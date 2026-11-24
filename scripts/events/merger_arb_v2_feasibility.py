"""Merger arbitrage, reconstructed so that what is left is alpha (D4): zero-trial feasibility.

    python3 scripts/events/merger_arb_v2_feasibility.py --today 2026-10-19
    python3 -m pytest scripts/events/tests/test_merger_arb_v2_feasibility.py

WHY THIS EXISTS
---------------
`results/events/MERGER_ARB_AND_IBKR_2026-10-15.md` found that equity merger
arbitrage, held as an index of deals, fails D4: its return is the deal-spread
risk premium, a short index put (Mitchell & Pulvino 2001). The team lead's
ruling of 2026-10-19 asks for a reconstruction in which what remains is alpha.
The note `results/events/MERGER_ARB_V2_2026-10-19.md` argues the case; this
script produces every number in it.

The reconstruction the note carries forward (design MA-HZ) is Giglio & Shue's
(2014) event-time result: the hazard of deal COMPLETION is hump-shaped in the
weeks after announcement, holders under-react to the passage of time, and so
deals earn more in their high-hazard weeks than in their low-hazard weeks
WITH THE SAME FACTOR EXPOSURES (their Tables 5-7). A long-high / short-low
book inside the deal cross-section therefore differences out the deal premium
and its crash kink, which is what D4 asks for. Whether that book can be built,
and whether D4's alpha leg (t >= 3.0) can be reached on the data we have, are
the questions here. The angles the note kills are measured here too where a
number decides them (E1 at IBKR: borrow against the effect).

WHAT IT MUST NEVER DO
---------------------
Read a price or return of any security, or compute any statistic of a
strategy. That is the trial (EVENTS 0 -> 1). Everything here is a COUNT, a
DATE, a FEE, a FLAG, a dollar volume, or arithmetic on published numbers:

* deal counts, announcement and completion DATES (EDGAR, committed in
  `results/events/merger_arb/edgar_deals.csv` by `merger_arb_feasibility.py`);
* the weekly hazard of completion, a statistic of deal OUTCOME TIMING, from
  those dates (no price enters). Every deal is administratively censored at
  2022-12-30, so no 2023+ date informs it (H13);
* how many deals sit in each event-time window each month, and how often a
  window book would trade (turnover, from dates alone);
* today's pending deals: Alpaca flags, IBKR fees and dollar ADV as read on
  2026-10-18 by `merger_arb_feasibility.py` (committed CSV; true on that date);
* the IBKR FEE_RATE panel (`data/cef/cef_borrow_history.parquet`): a cost;
* power of D4's alpha leg at information ratios implied by the published
  test statistics (`scripts/xasset/slate_feasibility.py` owns the arithmetic).

Inputs are committed files and `data/` panels only. No network, no
credentials, no broker. Nothing is written to `data/` (landmine 9).

DEFINITIONS (stated once, here)
-------------------------------
* ANNOUNCEMENT `ann`: the date of the deal's announcement document as found
  by `merger_arb_feasibility.py` (8-K item 1.01, SC 14D9 or 425; `doc_date`),
  else `d0`, the first deal filing, an UPPER bound on the announcement.
* COMPLETION: the target's Form 25 / 25-NSE date (`delist_date`) when the
  deal is `completed` (a 25 within two years of its last anchor).
* FAILURE has no date in the census (a target 8-K item 1.02 is mostly credit
  agreements: `EDGAR_EVENTS_2026-10-12.md` §5). Two brackets, both reported:
  (A) a not-completed deal leaves the risk set at its last anchor `a1`, which
  is early; (B) it stays until week 52, which is late. A conclusion that holds
  under both is not an artefact of the missing date.
* UNIVERSES, fixed before any count: CASH_1STEP = consideration class `cash`,
  not a tender offer; STOCK_1STEP = class `stock`, not a tender offer, with an
  acquirer CIK; TENDER_CASH = class `cash` tender offers, the NEGATIVE CONTROL
  (Giglio & Shue exclude tender offers because their expiry date makes the
  passage of time salient: the mechanism cannot operate there). Deals whose
  target registered shares in the window (holdco moves, reverse mergers) or
  whose target is ambiguous are excluded and counted.
* WINDOWS: Giglio & Shue §6.1, cash: Low 1 = event weeks 1-10, High = 12-35,
  Low 2 = 37-45 (cutoffs 11 and 36, the cutoff week itself left out). Equity
  cutoffs 15 and 41; the paper prints no example, so STOCK uses 1-14 / 16-40 /
  42-50 by the same rule [U: by analogy]. Event week = floor(days/7) + 1.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DEALS = REPO / "results/events/merger_arb/edgar_deals.csv"
PENDING = REPO / "results/events/merger_arb/pending_deals_2026-10-18.csv"
PENDING_READ_DATE = pd.Timestamp("2026-10-16")    # last Alpaca bar behind the ADV column; flags read 2026-10-18
G1A_SUMMARY = REPO / "results/events/g1a/g1a_summary_2026-10-13.json"
E1_HEDGE_SUMMARY = REPO / "results/events/e1_etf_hedge_summary_2026-10-15.json"
CEF_IBKR_TODAY = REPO / "results/events/merger_arb/cef_names_borrow_2026-10-18.csv"
BORROW = REPO / "data/cef/cef_borrow_history.parquet"
UNIVERSE = REPO / "data/cef/cef_universe.csv"
CALENDAR = REPO / "data/rv/etf_panel.parquet"     # SPY's row dates = NYSE sessions; no value is read
OUT = REPO / "results/events/merger_arb_v2"

FIT_START = pd.Timestamp("2010-01-01")
HOLDOUT_START = pd.Timestamp("2023-01-01")        # H13: sealed
ADMIN_CENSOR = pd.Timestamp("2022-12-30")         # last fit session; every deal is censored here
MAX_WEEK = 52
MIN_AT_RISK = 30                                  # a weekly hazard on fewer deals is printed, not summarised

GS_WINDOWS = {
    "cash": {"low1": (1, 10), "high": (12, 35), "low2": (37, 45)},
    "stock": {"low1": (1, 14), "high": (16, 40), "low2": (42, 50)},   # [U] by analogy, see docstring
}
UNIVERSE_WINDOWS = {"CASH_1STEP": "cash", "STOCK_1STEP": "stock", "TENDER_CASH": "cash"}

# Borrow-fee convention (docs/BRIEF.md §3, "The short side"): market value x fee / 360,
# market value marked to 102% of the prior settlement price.
FEE_DAY_COUNT = 360.0
FEE_COLLATERAL_MARKUP = 1.02
SESSIONS_PER_YEAR = 252.0
CAL_DAYS_PER_YEAR = 365.25

COST_GRID_BP = (5, 15, 30)

# ---------------------------------------------------------------------------
# Published inputs to the POWER ARITHMETIC ONLY. No decision rule reads them (H14).
# Giglio & Shue, "No News Is News", NBER WP 18914 (March 2013), published RFS
# 27(12) 2014; read 2026-10-19 (docs/REFERENCES.md §12ae). Each p-value is the
# paper's own one-sided test of High > Low, (a_high - a_low1) + (a_high - a_low2) > 0,
# or High > Buy-and-Hold; `years` is the span of calendar months it used.
# ---------------------------------------------------------------------------
GS_TESTS = [
    # key, label, one-sided p, years, source
    ("cash_full", "cash, High > Low, 1970-2010", 0.0084, 41.0, "Table 3"),
    ("equity_full", "equity, High > Low, 1970-2010", 0.0002, 41.0, "Table 3"),
    ("joint_high_gt_bh_full", "cash+equity, High > Buy&Hold, 1970-2010", 0.00615, 41.0, "Table 3"),
    ("cash_late", "cash, High > Low, 1991-2010, early-sample cutoffs", 0.2077, 20.0, "Table 4 Panel A"),
    ("equity_late", "equity, High > Low, 1991-2010, early-sample cutoffs", 0.0129, 20.0, "Table 4 Panel A"),
    ("joint_late", "cash+equity, High > Low, 1991-2010", 0.0271, 20.0, "Table 4 Panel A"),
    ("joint_high_gt_bh_late", "cash+equity, High > Buy&Hold, 1991-2010", 0.12055, 20.0, "Table 4 Panel A"),
]
# Table 8 (limits to arbitrage), cash deals, targets below the within-year median
# market cap: (alpha, s.e.) per month for High and Low 1. The paper prints no s.e.
# for the difference, so the IR is shown at two leg correlations [U].
GS_CASH_SMALL = {"high": (0.0113, 0.0024), "low1": (0.0001, 0.0021), "years": 41.0, "source": "Table 8"}
GS_SMALL_RHO = (0.0, 0.5)
# Alphas (per month, Fama-French) used only to put a gross scale beside the cost
# drag; the pair is (High, Low 1). Table 3 (full) and Table 4 Panel A (late), cash.
GS_CASH_ALPHA_BP = {"full": (64.0, -5.0), "late": (43.0, -3.0)}
MCLEAN_PONTIFF_KEEP = 0.42     # imported value is checked against slate_feasibility in the tests


# =========================================================================== guards
def assert_fit_only(dates: pd.Series, what: str) -> None:
    """Raise if any date reaches the sealed holdout. Every historical table calls this
    on the dates it is about to use, after censoring (H13)."""
    d = pd.to_datetime(pd.Series(dates)).dropna()
    if (d >= HOLDOUT_START).any():
        raise AssertionError(f"{what}: {int((d >= HOLDOUT_START).sum())} date(s) on/after "
                             f"{HOLDOUT_START.date()} would enter a fit-period table")


# =========================================================================== deals
def load_deals(path: Path = DEALS) -> pd.DataFrame:
    """The committed EDGAR census, with `ann` and the universe label.

    Raises on a missing column rather than inventing one."""
    need = {"deal", "target_cik", "d0", "a1", "doc_date", "doc_source", "tender", "final_class",
            "completed", "delist_date", "acquirer_cik", "target_rule", "target_registered", "freeze_out"}
    d = pd.read_csv(path, parse_dates=["d0", "a1", "delist_date", "doc_date"])
    miss = need - set(d.columns)
    if miss:
        raise KeyError(f"{path.name} lacks {sorted(miss)}")
    d["ann"], d["ann_basis"] = announcement_dates(d)
    d["universe"] = classify_universe(d)
    return d


def announcement_dates(d: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """`doc_date` where an announcement document was found, else `d0` (an upper bound).

    The census looked for the document in [d0 - 30d, d0 + 10d]; a doc_date outside
    that is a different filing and is not used."""
    ok = d["doc_date"].notna() & d["doc_source"].notna() \
        & (d["doc_date"] >= d["d0"] - pd.Timedelta(days=30)) \
        & (d["doc_date"] <= d["d0"] + pd.Timedelta(days=10))
    ann = d["d0"].where(~ok, d["doc_date"])
    basis = pd.Series(np.where(ok, "document", "d0_upper_bound"), index=d.index)
    return ann, basis


def classify_universe(d: pd.DataFrame) -> pd.Series:
    """The three universes of the docstring, or the reason a deal is out."""
    out = pd.Series("excluded_class", index=d.index, dtype=object)
    cash = d["final_class"].eq("cash")
    stock = d["final_class"].eq("stock") & d["acquirer_cik"].notna()
    tender = d["tender"].astype(bool)
    out[cash & ~tender] = "CASH_1STEP"
    out[stock & ~tender] = "STOCK_1STEP"
    out[cash & tender] = "TENDER_CASH"
    out[d["final_class"].eq("stock") & d["acquirer_cik"].isna() & ~tender] = "excluded_no_acquirer"
    bad = d["target_registered"].astype(bool) | d["target_rule"].eq("target_ambiguous")
    out[bad & out.isin(list(UNIVERSE_WINDOWS))] = "excluded_target_flag"
    return out


def exits(d: pd.DataFrame, bracket: str) -> pd.DataFrame:
    """Each deal's exit date and kind under a failure bracket, censored at ADMIN_CENSOR.

    kind: 'complete' (Form 25 on or before the censor), 'fail' (bracket A: the last
    anchor; bracket B: announcement + 52 weeks), or 'admin' (still open at the censor).
    A completion after the censor is NOT seen: the deal is open at the censor."""
    if bracket not in ("A", "B"):
        raise ValueError(f"bracket must be A or B, got {bracket!r}")
    comp = d["completed"].astype(bool) & d["delist_date"].notna() & (d["delist_date"] <= ADMIN_CENSOR)
    if bracket == "A":
        fail_at = d["a1"]
    else:
        fail_at = d["ann"] + pd.Timedelta(days=7 * MAX_WEEK)
    # a completed deal whose Form 25 falls after the censor is open at the censor
    not_comp_ever = ~d["completed"].astype(bool)
    when = pd.Series(ADMIN_CENSOR, index=d.index)
    kind = pd.Series("admin", index=d.index, dtype=object)
    when[comp] = d.loc[comp, "delist_date"]
    kind[comp] = "complete"
    f = not_comp_ever & (fail_at <= ADMIN_CENSOR)
    when[f] = fail_at[f]
    kind[f] = "fail"
    # a failure date before the announcement (an anchor that predates the document) exits in week 1
    when = when.where(when >= d["ann"], d["ann"])
    out = pd.DataFrame({"exit": when, "kind": kind})
    assert_fit_only(out["exit"], f"exits(bracket {bracket})")
    return out


def event_week(start: pd.Series, end: pd.Series) -> pd.Series:
    """floor(days / 7) + 1: day 0-6 after announcement is week 1."""
    return ((end - start).dt.days // 7 + 1).astype(int)


# =========================================================================== hazard
def completion_hazard(ann: pd.Series, exit_date: pd.Series, kind: pd.Series,
                      max_week: int = MAX_WEEK) -> pd.DataFrame:
    """Weekly Kaplan-Meier hazard of COMPLETION, failures and admin exits censored.

    A deal is at risk in week w if its exit week >= w; it completes in week w if its
    exit is a completion in week w. A deal censored in week w is at risk in w and
    not an event. Returns one row per week 1..max_week."""
    wk = event_week(ann, exit_date)
    if (wk < 1).any():
        raise ValueError(f"{int((wk < 1).sum())} exit(s) before their announcement")
    rows = []
    for w in range(1, max_week + 1):
        at_risk = int((wk >= w).sum())
        events = int(((wk == w) & (kind == "complete")).sum())
        rows.append({"week": w, "at_risk": at_risk, "completions": events,
                     "hazard": events / at_risk if at_risk else np.nan})
    return pd.DataFrame(rows)


def hazard_summary(h: pd.DataFrame, windows: dict) -> dict:
    """Where the hazard is above its own mean, against Giglio & Shue's windows.

    No new parameter: the mean is over the weeks with at least MIN_AT_RISK deals at
    risk; agreement is the share of the paper's High weeks above that mean and of its
    Low weeks below it."""
    ok = h[h["at_risk"] >= MIN_AT_RISK]
    if ok.empty:
        raise ValueError("no week has enough deals at risk")
    m = ok["hazard"].mean()
    above = ok.loc[ok["hazard"] > m, "week"]
    hi_lo, hi_hi = windows["high"]
    hi_weeks = ok[(ok["week"] >= hi_lo) & (ok["week"] <= hi_hi)]
    lo_weeks = ok[((ok["week"] >= windows["low1"][0]) & (ok["week"] <= windows["low1"][1]))
                  | ((ok["week"] >= windows["low2"][0]) & (ok["week"] <= windows["low2"][1]))]
    return {
        "weeks_summarised": int(len(ok)),
        "mean_weekly_hazard": float(m),
        "peak_week": int(ok.loc[ok["hazard"].idxmax(), "week"]),
        "peak_hazard": float(ok["hazard"].max()),
        "first_week_above_mean": int(above.min()) if len(above) else None,
        "last_week_above_mean": int(above.max()) if len(above) else None,
        "share_gs_high_weeks_above_mean": float((hi_weeks["hazard"] > m).mean()) if len(hi_weeks) else None,
        "share_gs_low_weeks_below_mean": float((lo_weeks["hazard"] <= m).mean()) if len(lo_weeks) else None,
        "hazard_mean_in_gs_high": float(hi_weeks["hazard"].mean()) if len(hi_weeks) else None,
        "hazard_mean_in_gs_low1": float(ok[(ok["week"] >= windows["low1"][0]) & (ok["week"] <= windows["low1"][1])]["hazard"].mean()),
    }


# =========================================================================== windows
def window_spells(ann: pd.Series, exit_date: pd.Series, kind: pd.Series, lo: int, hi: int) -> pd.DataFrame:
    """Each deal's spell inside event weeks [lo, hi]: entry, exit, and whether the exit
    is PAID (a trade) or free.

    Entry is the start of week lo, if the deal is still open then. The spell ends at
    the end of week hi, or at the deal's exit if earlier. A COMPLETION ends a position
    at no cost (cash paid out, or the target converts into the acquirer and closes the
    short); a window end or a failure is a paid trade; the admin censor is neither
    (the position is open when the fit window ends)."""
    entry = ann + pd.to_timedelta(7 * (lo - 1), unit="D")
    wend = ann + pd.to_timedelta(7 * hi, unit="D")
    alive = exit_date > entry
    end = pd.concat([wend, exit_date], axis=1).min(axis=1)
    by_exit = exit_date <= wend
    paid_exit = np.where(by_exit, kind.isin(["fail"]), True)
    admin = by_exit & kind.eq("admin")
    paid_exit = np.where(admin, False, paid_exit)
    # a window end that falls after the admin censor is not a trade either
    paid_exit = np.where(~by_exit & (wend > ADMIN_CENSOR), False, paid_exit)
    end = end.where(end <= ADMIN_CENSOR, ADMIN_CENSOR)
    sp = pd.DataFrame({"entry": entry, "end": end, "paid_exit": paid_exit.astype(bool)})
    sp = sp[alive & (sp["entry"] <= ADMIN_CENSOR)]
    return sp


def leg_turnover(spells: pd.DataFrame, start: pd.Timestamp = FIT_START,
                 stop: pd.Timestamp = ADMIN_CENSOR) -> dict:
    """Turnover of a leg that holds one unit of notional per deal while in window.

    turnover per unit of leg gross per year = paid trades per year / average number of
    concurrent positions. Each entry is a paid trade; exits as `window_spells` marks."""
    assert_fit_only(spells["end"], "leg_turnover")
    days = (stop - start).days
    years = days / CAL_DAYS_PER_YEAR
    s = spells[(spells["entry"] >= start) & (spells["entry"] <= stop)]
    held_days = (s["end"] - s["entry"]).dt.days.clip(lower=0).sum()
    avg_conc = held_days / days
    trades = len(s) + int(s["paid_exit"].sum())
    out = {"positions": int(len(s)), "paid_exits": int(s["paid_exit"].sum()),
           "free_exits": int(len(s) - s["paid_exit"].sum()), "avg_concurrent": float(avg_conc),
           "paid_trades_per_year": float(trades / years)}
    out["turnover_per_unit_gross_per_year"] = float(out["paid_trades_per_year"] / avg_conc) if avg_conc > 0 else np.nan
    for c in COST_GRID_BP:
        out[f"cost_drag_bp_per_year_at_{c}bp"] = out["turnover_per_unit_gross_per_year"] * c
    return out


def monthly_breadth(spells: pd.DataFrame, month_ends: pd.DatetimeIndex) -> pd.Series:
    """Number of deals inside the window at each month-end."""
    e = spells["entry"].values
    x = spells["end"].values
    return pd.Series([int(((e <= m) & (x > m)).sum()) for m in month_ends.values], index=month_ends)


def session_calendar() -> pd.DatetimeIndex:
    """NYSE sessions: the dates on which SPY has a row in the research ETF panel.
    Only the date column is read."""
    c = pd.read_parquet(CALENDAR, columns=["date", "ticker"])
    cal = pd.DatetimeIndex(sorted(pd.to_datetime(c.loc[c["ticker"] == "SPY", "date"]).unique()))
    if cal.max() < ADMIN_CENSOR:
        raise ValueError(f"calendar ends {cal.max().date()}, before the fit window does")
    return cal


def fit_month_ends(cal: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(cal[(cal >= FIT_START) & (cal <= ADMIN_CENSOR)])
    return pd.DatetimeIndex(s.groupby(s.dt.to_period("M")).max().values)


# =========================================================================== power
def ir_from_one_sided_p(p: float, years: float) -> float:
    """The annual information ratio a one-sided p-value implies over `years`:
    z = Phi^-1(1 - p), IR = z / sqrt(years). Arithmetic on a published test, not an
    estimate of our sleeve's IR."""
    from statistics import NormalDist
    if not 0 < p < 1:
        raise ValueError(f"p must be in (0, 1), got {p}")
    return NormalDist().inv_cdf(1 - p) / math.sqrt(years)


def ir_from_leg_alphas(high: tuple, low: tuple, rho: float, years: float) -> float:
    """IR of High minus Low from per-month (alpha, s.e.) pairs at an assumed leg
    correlation: t = (a_h - a_l) / sqrt(se_h^2 + se_l^2 - 2 rho se_h se_l), IR = t / sqrt(years)."""
    (ah, sh), (al, sl) = high, low
    se = math.sqrt(sh ** 2 + sl ** 2 - 2 * rho * sh * sl)
    return (ah - al) / se / math.sqrt(years)


def published_irs() -> list[tuple]:
    """(key, label, ir, paper_years, source) for every published input, IRs computed here."""
    out = [(k, lab, ir_from_one_sided_p(p, y), y, f"{src}, one-sided p {p}") for k, lab, p, y, src in GS_TESTS]
    for rho in GS_SMALL_RHO:
        ir = ir_from_leg_alphas(GS_CASH_SMALL["high"], GS_CASH_SMALL["low1"], rho, GS_CASH_SMALL["years"])
        out.append((f"cash_small_rho{rho}", f"cash, small targets, High - Low1, legs rho={rho} [U]", ir,
                     GS_CASH_SMALL["years"], GS_CASH_SMALL["source"]))
    return out


def power_table(cal: pd.DatetimeIndex) -> pd.DataFrame:
    """P(alpha t >= 3) and P(deflated Sharpe passes at EVENTS N = 1) for each
    published IR, on two fit windows.

    WINDOW 'edgar_2010': the first P&L a High-window position can earn is week 12 of a
    deal announced in the census's first week (2010-01-04) plus H1's two sessions, to
    2022-12-30. WINDOW 'edgar_2001' is the same rule on a census rebuilt from 2001,
    which does not exist yet: it is the window a pre-registration would need."""
    from scripts.xasset.slate_feasibility import alpha_t_bar, p_alpha_t, power, required_sharpe
    rows = []
    for wname, first_ann in (("edgar_2010", pd.Timestamp("2010-01-04")),
                             ("edgar_2001", pd.Timestamp("2001-01-02"))):
        first_pos = first_ann + pd.Timedelta(days=7 * (GS_WINDOWS["cash"]["high"][0] - 1))
        i = cal.searchsorted(first_pos)
        first_pnl = cal[i + 2]                                      # H1: decide t, fill t+1, earn t+2
        T = int(((cal >= first_pnl) & (cal < HOLDOUT_START)).sum())
        for key, label, ir, yrs, src in published_irs():
            for scale_name, scale in (("as published", 1.0), ("x0.42 post-publication", MCLEAN_PONTIFF_KEEP)):
                irs = ir * scale
                rows.append({"window": wname, "first_pnl": first_pnl.date(), "sessions": T,
                             "years": round(T / SESSIONS_PER_YEAR, 2), "test": key, "label": label,
                             "source": src, "paper_years": yrs,
                             "scale": scale_name, "ir": round(irs, 3),
                             "ir_needed_alpha_t3": round(alpha_t_bar(T), 3),
                             "p_alpha_t_ge_3": round(p_alpha_t(irs, T), 4),
                             "sr_needed_dsr_n1": round(required_sharpe(1, T), 3),
                             "p_dsr_pass_n1": round(power(irs, 1, T), 4)})
    return pd.DataFrame(rows)


# =========================================================================== pending
def pending_by_window(deals: pd.DataFrame, path: Path = PENDING, asof: pd.Timestamp = PENDING_READ_DATE) -> pd.DataFrame:
    """Today's pending deals, by universe and by the event-time window they sit in.

    `ann` comes from the census row with the same target and d0 where there is one
    (its announcement document); otherwise d0, which for a 425-sourced deal is the first
    425 (normally the announcement day) and for an anchored deal an upper bound."""
    p = pd.read_csv(path, parse_dates=["d0"])
    need = {"target_cik", "d0", "final_class", "tender", "acquirer_ticker_today", "tgt_alp_shortable",
            "tgt_ibkr_fee_pct", "tgt_adv_usd", "acq_alp_shortable", "acq_ibkr_fee_pct", "stale"}
    miss = need - set(p.columns)
    if miss:
        raise KeyError(f"{path.name} lacks {sorted(miss)}")
    dup = deals.duplicated(["target_cik", "d0"], keep=False)
    if dup.any():
        raise ValueError(f"{int(dup.sum())} census rows share a (target_cik, d0) key; the lookup would be ambiguous")
    look = dict(zip(zip(deals["target_cik"], deals["d0"]), deals["ann"]))
    found = [look.get(k) for k in zip(p["target_cik"], p["d0"])]
    p["ann_basis"] = ["census" if f is not None else "d0" for f in found]
    # no census row: d0 itself is the stated basis (a first 425, or an upper bound), labelled above
    p["ann"] = [f if f is not None else d for f, d in zip(found, p["d0"])]
    p["ann"] = pd.to_datetime(p["ann"])
    p["week"] = ((asof - p["ann"]).dt.days // 7 + 1).astype(int)
    cash = p["final_class"].eq("cash")
    stock = p["final_class"].eq("stock") & p["acquirer_ticker_today"].notna()
    tender = p["tender"].astype(bool)
    p["universe"] = np.select([cash & ~tender, stock & ~tender, cash & tender],
                              ["CASH_1STEP", "STOCK_1STEP", "TENDER_CASH"], "other")

    def win(r):
        if r["universe"] == "other":
            return "n/a"
        w = GS_WINDOWS[UNIVERSE_WINDOWS[r["universe"]]]
        for name, (lo, hi) in w.items():
            if lo <= r["week"] <= hi:
                return name
        return "gap" if r["week"] <= w["low2"][1] else "beyond"
    p["window"] = p.apply(win, axis=1)
    return p


def summarise_pending(p: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (u, w), g in p[p["universe"] != "other"].groupby(["universe", "window"]):
        flag = g["tgt_alp_shortable"].dropna().astype(bool)
        fee = g["tgt_ibkr_fee_pct"].dropna()
        adv = g["tgt_adv_usd"].dropna()
        rows.append({"universe": u, "window": w, "deals": len(g), "stale_425": int(g["stale"].astype(bool).sum()),
                     "target_alpaca_shortable": f"{int(flag.sum())}/{len(flag)}",
                     "target_ibkr_listed": int(len(fee)),
                     "target_ibkr_fee_median_pct": round(float(fee.median()), 2) if len(fee) else None,
                     "target_ibkr_fee_max_pct": round(float(fee.max()), 2) if len(fee) else None,
                     "target_adv_median_usd": round(float(adv.median())) if len(adv) else None,
                     "adv_ge_0.2m (fits $10k at 5%)": int((adv >= 2e5).sum()),
                     "adv_ge_2m (fits $100k at 5%)": int((adv >= 2e6).sum()),
                     "acquirer_alpaca_shortable": (f"{int(g['acq_alp_shortable'].dropna().astype(bool).sum())}/"
                                                   f"{int(g['acq_alp_shortable'].notna().sum())}") if u == "STOCK_1STEP" else ""})
    return pd.DataFrame(rows)


# =========================================================================== E1 at IBKR
def borrow_cost_bp(fee_pct_per_year: float, calendar_days: float) -> float:
    """Borrow charged on $1 short over `calendar_days`, in bp: fee x days / 360 on 102%."""
    return fee_pct_per_year * 100.0 * calendar_days / FEE_DAY_COUNT * FEE_COLLATERAL_MARKUP


def e1_ibkr_borrow() -> tuple[pd.DataFrame, dict]:
    """E1 (long CEF merger target, short acquirer) at IBKR: is the acquirer's borrow
    smaller than the effect it hedges?

    The effect and the hold are READ from the E1 gate's committed summary (produced by
    `e1_etf_hedge_gate.py` from CRSP, pre-2023): the muni median of the acquirer-pair
    return and the muni median hold in sessions. Fees are IBKR FEE_RATE (2021-09 on)
    for the universe muni acquirers G1a listed, over each merger window, against the
    same fund's 120 sessions before it and the other universe munis on the same days,
    plus today's IBKR file. Fees are costs, not returns."""
    e1 = json.loads(E1_HEDGE_SUMMARY.read_text())
    try:
        eff = float(e1["effect_rem_measured"]["muni"]["median"])
        hold_sessions = float(e1["holds_sessions"]["muni"])
    except KeyError as k:
        raise KeyError(f"{E1_HEDGE_SUMMARY.name} lacks {k}") from None
    hold_days = hold_sessions * CAL_DAYS_PER_YEAR / SESSIONS_PER_YEAR
    g1a = json.loads(G1A_SUMMARY.read_text())
    eps = pd.DataFrame(g1a["H1b_universe_acquirers_fee_at_first_filing"])
    b = pd.read_parquet(BORROW)
    piv = b.pivot(index="date", columns="ticker", values="fee_rate_pct").sort_index()
    uni = pd.read_csv(UNIVERSE)
    munis = sorted(uni.loc[uni["grp"] == "muni", "ticker"])
    rows = []
    for _, e in eps.iterrows():
        f, l = pd.Timestamp(e["first_merger_filing"]), pd.Timestamp(e["last_merger_filing"])
        if e["acquirer"] not in piv.columns:
            raise KeyError(f"no FEE_RATE series for {e['acquirer']}")
        s = piv[e["acquirer"]]
        win = s[(s.index >= f) & (s.index <= l)].dropna()
        pre = s[s.index < f].dropna().tail(120)
        others = [m for m in munis if m in piv.columns and m != e["acquirer"]]
        xs = piv.loc[(piv.index >= f) & (piv.index <= l), others].median(axis=1) if len(win) > 1 else pd.Series(dtype=float)
        mean_win = float(win.mean()) if len(win) > 1 else np.nan
        rows.append({"acquirer": e["acquirer"], "segment": e["segment"], "first_filing": f.date(),
                     "last_filing": l.date(), "window_sessions": int(len(win)),
                     "fee_at_first_filing_pct": e["fee_rate_pct"],
                     "fee_mean_in_window_pct": round(mean_win, 2) if len(win) > 1 else None,
                     "fee_mean_120_before_pct": round(float(pre.mean()), 2) if len(pre) else None,
                     "other_munis_median_in_window_pct": round(float(xs.mean()), 2) if len(xs) else None,
                     "borrow_over_muni_hold_bp": round(borrow_cost_bp(mean_win, hold_days), 1) if len(win) > 1 else None})
    t = pd.DataFrame(rows)
    today = pd.read_csv(CEF_IBKR_TODAY)
    tm = today[today["symbol"].isin(munis)].dropna(subset=["ibkr_fee_pct"])
    win_means = t.loc[t["segment"].eq("muni") & t["fee_mean_in_window_pct"].notna(), "fee_mean_in_window_pct"]
    summ = {
        "muni_effect_median_bp": round(eff * 1e4, 1),
        "muni_hold_sessions": hold_sessions,
        "muni_hold_calendar_days": round(hold_days, 1),
        "muni_windows_with_fee_path": int(len(win_means)),
        "muni_window_fee_mean_median_pct": round(float(win_means.median()), 2),
        "muni_windows_borrow_ge_effect": int((win_means.apply(lambda x: borrow_cost_bp(x, hold_days)) >= eff * 1e4).sum()),
        "muni_today_ibkr_fee_median_pct": round(float(tm["ibkr_fee_pct"].median()), 2),
        "muni_today_ibkr_fee_min_pct": round(float(tm["ibkr_fee_pct"].min()), 2),
        "muni_today_borrow_over_hold_bp_at_median": round(borrow_cost_bp(float(tm["ibkr_fee_pct"].median()), hold_days), 1),
        "muni_today_borrow_over_hold_bp_at_min": round(borrow_cost_bp(float(tm["ibkr_fee_pct"].min()), hold_days), 1),
        "muni_today_names": tm["symbol"].tolist(),
        "today_file": CEF_IBKR_TODAY.name,
    }
    return t, summ


# =========================================================================== main
def universe_by_year(d: pd.DataFrame) -> pd.DataFrame:
    fit = d[(d["ann"] >= FIT_START) & (d["ann"] < HOLDOUT_START)]
    t = pd.crosstab(fit["ann"].dt.year, fit["universe"])
    t["all"] = t.sum(axis=1)
    return t


def acquirer_identification_bias(d: pd.DataFrame) -> pd.DataFrame:
    """Share of deals with an identified acquirer CIK, completed vs not, by class,
    announcements 2010-2020. STOCK_1STEP requires an acquirer; if identification
    is likelier for deals that completed, that universe is conditioned on the outcome."""
    x = d[(d["ann"] >= FIT_START) & (d["ann"] < pd.Timestamp("2021-01-01"))]
    rows = []
    for c, g in x.groupby("final_class"):
        for comp, h in g.groupby(g["completed"].astype(bool)):
            rows.append({"final_class": c, "completed": comp, "deals": len(h),
                         "acquirer_identified": int(h["acquirer_cik"].notna().sum()),
                         "share": round(float(h["acquirer_cik"].notna().mean()), 3)})
    return pd.DataFrame(rows)


def not_completed_by_year(d: pd.DataFrame) -> pd.DataFrame:
    """Not completed within two years of the last anchor, for announcements to 2020 only:
    a 2021-22 deal's two-year window runs into the sealed years. An UPPER bound on
    breaks (the bucket also holds asset sales and reverse mergers the target survives)."""
    x = d[(d["ann"] >= FIT_START) & (d["ann"] < pd.Timestamp("2021-01-01")) & d["universe"].isin(list(UNIVERSE_WINDOWS))]
    return pd.crosstab(x["ann"].dt.year, [x["universe"], x["completed"]])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--today", required=True, help="run date; names the output files (YYYY-MM-DD)")
    a = ap.parse_args(argv)
    today = pd.Timestamp(a.today).date()
    OUT.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 220)

    d = load_deals()
    print(f"census: {len(d)} deals, announcements {d['ann'].min().date()} -> {d['ann'].max().date()} "
          f"({DEALS.relative_to(REPO)})")
    fit = d[(d["ann"] >= FIT_START) & (d["ann"] < HOLDOUT_START)].copy()
    uby = universe_by_year(d)
    uby.to_csv(OUT / "universe_by_year.csv")
    print("\nuniverse by announcement year (fit years only):\n", uby.to_string())
    basis = pd.crosstab(fit["universe"], fit["ann_basis"])
    print("\nannouncement basis:\n", basis.to_string())

    cal = session_calendar()
    mends = fit_month_ends(cal)
    haz_rows, haz_sum, turn_rows, breadth_rows = [], [], [], []
    for u, wkey in UNIVERSE_WINDOWS.items():
        g = fit[fit["universe"] == u]
        for br in ("A", "B"):
            ex = exits(g, br)
            h = completion_hazard(g["ann"], ex["exit"], ex["kind"])
            h.insert(0, "bracket", br)
            h.insert(0, "universe", u)
            haz_rows.append(h)
            s = hazard_summary(h, GS_WINDOWS[wkey])
            s.update({"universe": u, "bracket": br, "deals": int(len(g)),
                      "completed_by_censor": int(ex["kind"].eq("complete").sum()),
                      "failed_exit": int(ex["kind"].eq("fail").sum()),
                      "open_at_censor": int(ex["kind"].eq("admin").sum())})
            haz_sum.append(s)
            spells_all = []
            for leg, (lo, hi) in GS_WINDOWS[wkey].items():
                sp = window_spells(g["ann"], ex["exit"], ex["kind"], lo, hi)
                spells_all.append(sp.assign(leg=leg))
                t = leg_turnover(sp)
                t.update({"universe": u, "bracket": br, "leg": leg, "weeks": f"{lo}-{hi}"})
                turn_rows.append(t)
                mb = monthly_breadth(sp, mends)
                breadth_rows.append({"universe": u, "bracket": br, "leg": leg, "months": len(mb),
                                     "median": float(mb.median()), "p10": float(mb.quantile(0.1)),
                                     "p90": float(mb.quantile(0.9)), "min": int(mb.min()),
                                     "months_below_5": int((mb < 5).sum())})
            low = pd.concat([x for x in spells_all if x["leg"].iloc[0] != "high"]) if len(spells_all) else None
            t = leg_turnover(low)
            t.update({"universe": u, "bracket": br, "leg": "low1+low2", "weeks": "both low windows"})
            turn_rows.append(t)
    # robustness: d0 is an UPPER bound on the announcement, which understates event
    # weeks and would shift the hump EARLIER. The same summary on document-dated deals only.
    for u, wkey in UNIVERSE_WINDOWS.items():
        g = fit[(fit["universe"] == u) & (fit["ann_basis"] == "document")]
        for br in ("A", "B"):
            ex = exits(g, br)
            h = completion_hazard(g["ann"], ex["exit"], ex["kind"])
            h.insert(0, "bracket", br)
            h.insert(0, "universe", u + "|document_dated")
            haz_rows.append(h)
            s_ = hazard_summary(h, GS_WINDOWS[wkey])
            s_.update({"universe": u + "|document_dated", "bracket": br, "deals": int(len(g)),
                       "completed_by_censor": int(ex["kind"].eq("complete").sum()),
                       "failed_exit": int(ex["kind"].eq("fail").sum()),
                       "open_at_censor": int(ex["kind"].eq("admin").sum())})
            haz_sum.append(s_)
    haz = pd.concat(haz_rows)
    haz.to_csv(OUT / "hazard_weekly.csv", index=False)
    hs = pd.DataFrame(haz_sum)
    hs.to_csv(OUT / "hazard_summary.csv", index=False)
    tr = pd.DataFrame(turn_rows)
    tr.to_csv(OUT / "turnover.csv", index=False)
    brd = pd.DataFrame(breadth_rows)
    brd.to_csv(OUT / "breadth_monthly.csv", index=False)
    print("\nhazard summary:\n", hs.to_string(index=False))
    print("\nturnover:\n", tr.to_string(index=False))
    print("\nbreadth at month-ends:\n", brd.to_string(index=False))

    # the L/S cost drag per unit of TOTAL gross (half long High, half short Low1+Low2),
    # beside the gross a published alpha pair implies (arithmetic, labelled)
    ls_rows = []
    for (u, br), g in tr[tr["universe"].isin(["CASH_1STEP", "STOCK_1STEP"])].groupby(["universe", "bracket"]):
        th = float(g.loc[g["leg"] == "high", "turnover_per_unit_gross_per_year"].iloc[0])
        tl = float(g.loc[g["leg"] == "low1+low2", "turnover_per_unit_gross_per_year"].iloc[0])
        row = {"universe": u, "bracket": br, "turnover_ls_per_unit_total_gross": round(0.5 * th + 0.5 * tl, 2)}
        for c in COST_GRID_BP:
            row[f"drag_bp_at_{c}"] = round((0.5 * th + 0.5 * tl) * c, 1)
        ls_rows.append(row)
    ls = pd.DataFrame(ls_rows)
    gross = {k: round((h - l) / 2 * 12, 1) for k, (h, l) in GS_CASH_ALPHA_BP.items()}
    gross["full_x0.42"] = round(gross["full"] * MCLEAN_PONTIFF_KEEP, 1)
    ls.to_csv(OUT / "ls_cost_drag.csv", index=False)
    print("\nL/S cost drag per unit of total gross, bp/yr:\n", ls.to_string(index=False))
    print("GS cash High-minus-Low1 alpha per unit of total gross, bp/yr (arithmetic on published alphas):", gross)

    pw = power_table(cal)
    pw.to_csv(OUT / "power.csv", index=False)
    print("\npower of D4's alpha leg (and the N=1 deflated Sharpe):\n",
          pw[["window", "years", "test", "scale", "ir", "ir_needed_alpha_t3", "p_alpha_t_ge_3", "p_dsr_pass_n1"]].to_string(index=False))

    pend = pending_by_window(d)
    ps = summarise_pending(pend)
    ps.to_csv(OUT / f"pending_by_window_{today}.csv", index=False)
    print(f"\npending deals by window as of {PENDING_READ_DATE.date()} (flags read 2026-10-18):\n", ps.to_string(index=False))

    e1t, e1s = e1_ibkr_borrow()
    e1t.to_csv(OUT / "e1_ibkr_borrow.csv", index=False)
    print("\nE1 at IBKR, acquirer borrow:\n", e1t.to_string(index=False))
    print(json.dumps(e1s, indent=1))

    aib = acquirer_identification_bias(d)
    aib.to_csv(OUT / "acquirer_identification_bias.csv", index=False)
    print("\nacquirer identified, by class and outcome, announcements 2010-2020:\n", aib.to_string(index=False))

    ncy = not_completed_by_year(d)
    ncy.to_csv(OUT / "not_completed_by_year.csv")
    print("\nnot completed within two years, announcements 2010-2020 (upper bound on breaks):\n", ncy.to_string())

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_date": str(today), "zero_trials": True,
        "inputs": {"deals": str(DEALS.relative_to(REPO)), "pending": str(PENDING.relative_to(REPO)),
                   "g1a": str(G1A_SUMMARY.relative_to(REPO)), "e1_hedge": str(E1_HEDGE_SUMMARY.relative_to(REPO)),
                   "borrow_panel": str(BORROW.relative_to(REPO)),
                   "borrow_panel_last": str(pd.read_parquet(BORROW, columns=["date"])["date"].max().date()),
                   "calendar_last": str(cal.max().date())},
        "admin_censor": str(ADMIN_CENSOR.date()),
        "fit_universe_counts": {k: int(v) for k, v in fit["universe"].value_counts().items()},
        "announcement_basis": {f"{u}|{b}": int(n) for (u, b), n in fit.groupby(["universe", "ann_basis"]).size().items()},
        "hazard_summary": hs.to_dict(orient="records"),
        "breadth": brd.to_dict(orient="records"),
        "ls_cost_drag": ls.to_dict(orient="records"),
        "gs_cash_ls_gross_bp_per_year_per_unit_total_gross": gross,
        "power": pw.to_dict(orient="records"),
        "pending_by_window": ps.to_dict(orient="records"),
        "e1_ibkr": e1s,
        "acquirer_identification_bias": aib.to_dict(orient="records"),
        "pending_ann_basis": pend.loc[pend["universe"] != "other", "ann_basis"].value_counts().to_dict(),
    }
    (OUT / f"summary_{today}.json").write_text(json.dumps(summary, indent=1, default=str))
    print(f"\nwrote {OUT.relative_to(REPO)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
