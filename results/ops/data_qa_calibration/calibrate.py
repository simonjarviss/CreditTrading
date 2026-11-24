"""Derive `scripts/ops/data_qa.py`'s thresholds on fit data, to the design's false-alarm budget.

    python3 results/ops/data_qa_calibration/calibrate.py [--out OUT.json]

Zero trials: this calibrates a report-only data check, and no result here is a claim about
returns. Output of record: `calibration_2026-11-08.json` next to this file; the note is
`results/ops/DATA_QA_CALIBRATION_2026-11-08.md`.

FIT ONLY (H13). Every RATE below is computed on 2005-01-01..2022-12-31 (H5's eras; 2023 onward is
the time holdout and is not read for any rate or for choosing anything). Each book's deployed
names only: the core's 13 from the frozen spec, C4's 74 from its frozen universe. The sealed
CEFs outside the deployed universe never enter. Recall on the known positives reads only each
positive's own name-days (the IGR step of 2026-09-08 sits after 2022 and is read only as that
one name-day window).

THE BUDGET. The design's: at most one flag per book per week on panels with no known defect,
jointly over the five checks with a free threshold, so each of Q2..Q6 gets 0.2 flags per week
(`data_qa.BUDGET_SHARE`). Each threshold is DERIVED: the least strict value on a declared grid
whose flag rate on the fit panel is at or under that share, then the rate one grid step either side is
printed so a cliff shows (H8). Nothing here is tuned against the recall.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
from scripts.ops import data_qa as q        # noqa: E402

FIT_START, FIT_END = pd.Timestamp("2005-01-01"), pd.Timestamp("2022-12-31")
Q6_FIT_START = pd.Timestamp("2013-01-01")   # landmine 8: before 2013 the book is flat, so the
#                                             "one ADV dip from thin" question has no answer there
DATA = {"cef": Path.home() / "quantt_data" / "cef", "c4": Path.home() / "quantt_data" / "cef_families"}
RULINGS = REPO / "results/cef/prereg_c4_level/dgl3_rulings_2026-11-03.csv"
THIN = REPO / "results/backtests/thin-days-2026-11-03/sleeve_thin.csv"
BUDGET = q.BUDGET_FLAGS_PER_WEEK * q.BUDGET_SHARE
Z_GRID = np.round(np.arange(4.0, 60.01, 0.5), 1)
DELTA_GRID = list(range(0, 40))
LINE_GRID = np.round(np.arange(0.20, 2.0001, 0.01), 2)
MARGIN_GRID = np.round(np.arange(0.0, 1.0001, 0.005), 3)
# Q4 positives: the design's list, dates from results/cef/data_guards/split_basis_scan_2026-10-20.txt
Q4_POS = {"cef": [], "c4": [("IGR", "2026-09-08"), ("BTO", "2008-12-30"), ("TYG", "2020-05-01"),
                            ("NXG", "2020-06-15"), ("EMO", "2020-07-28")]}


def weeks(idx) -> float:
    return (idx.max() - idx.min()).days / 7.0


def masks_for(book):
    df = pd.read_csv(RULINGS)
    df = df[df["ruling"].str.startswith("MASK")].copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


def known_positive_windows(masks: pd.DataFrame) -> set:
    """(ticker, session date) near each mask: a positive is not a false alarm."""
    out = set()
    for _, r in masks.iterrows():
        for k in range(-3, 6):
            out.add((r["ticker"], r["date"] + pd.Timedelta(days=k)))
    return out


def run_book(book: str) -> dict:
    cfg = q.BOOKS[book]
    spec = q.read_spec(cfg)
    uni = q.book_universe(cfg, spec)
    data_dir = DATA[book]
    p = q.load_panels(data_dir, uni)
    fit = {k: getattr(p, k).loc[FIT_START:FIT_END] for k in ("close", "volume", "nav")}
    wk = weeks(fit["nav"].index)
    out: dict = {"book": book, "fit_nav_dates": [str(fit["nav"].index.min().date()), str(fit["nav"].index.max().date())],
                 "fit_weeks": round(wk, 1), "n_names": len(uni), "panel_last": str(p.nav.index.max().date()),
                 "data_dir": str(data_dir).replace(str(Path.home()), "~"), "budget_flags_per_week_per_check": BUDGET, "note": []}

    # ---------------------------------------------------------------- Q1 (row counts, no free threshold)
    counts = {}
    for label in ("close", "nav"):
        f = fit[label]
        n = f.notna().sum(axis=1)
        d = (n.diff().fillna(0) != 0)
        counts[label] = {"rows_differ_nights": int(d.sum()), "per_week": round(float(d.sum()) / weeks(f.index), 3)}
    out["Q1"] = {"row_count_rate": counts}

    # ---------------------------------------------------------------- Q2
    masks = masks_for(book)
    in_book = masks[masks["ticker"].isin(uni)]
    exclude = known_positive_windows(masks)
    cand_full = q.q2_candidates(p.nav.loc[FIT_START:FIT_END + pd.Timedelta(days=10)], p.close)
    cand = cand_full[(cand_full["date"] >= FIT_START) & (cand_full["date"] <= FIT_END)]
    clean = cand.loc[np.array([(t, d) not in exclude for t, d in zip(cand["ticker"], cand["date"])], dtype=bool)]
    def rate(z):
        return float((clean["z"] >= z).sum()) / wk
    z_star = next((float(z) for z in Z_GRID if rate(z) <= BUDGET), None)
    rec = []
    for _, r in in_book.iterrows():
        d = r["date"]
        hit = cand[(cand["ticker"] == r["ticker"]) & (cand["date"] <= d) &
                   (cand["span_end"].fillna(cand["date"]) >= d) & (cand["z"] >= (z_star or np.inf))]
        rec.append({"ticker": r["ticker"], "date": str(d.date()), "flagged": len(hit) > 0,
                    "z": None if hit.empty else round(float(hit["z"].max()), 2)})
    rows = sum(x["flagged"] for x in rec)
    out["Q2"] = {"z_threshold": z_star, "flags_per_week": None if z_star is None else round(rate(z_star), 3),
                 "plateau": {str(z): round(rate(z), 3) for z in ((z_star or 0) - 0.5, (z_star or 0) + 0.5)},
                 "reverted_share_at_z": None if z_star is None else round(float(clean[clean.z >= z_star].reverted.mean()), 3),
                 "recall": rec, "recall_rows": f"{rows}/{len(rec)}",
                 "n_positives_in_book": int(len(in_book))}

    # ---------------------------------------------------------------- Q3
    streak = q.q3_candidates(p.nav.loc[FIT_START:FIT_END], 0)
    def q3_rate(delta):
        over = streak[streak["L"] > streak["prior_max"] + delta]
        runs = over.groupby(["ticker", "run_start"]).head(1)
        return len(runs) / wk, len(over) / wk
    delta_star = next((d for d in DELTA_GRID if q3_rate(d)[0] <= BUDGET), None)
    out["Q3"] = {"delta": delta_star, "new_runs_per_week": None if delta_star is None else round(q3_rate(delta_star)[0], 3),
                 "flag_nights_per_week": None if delta_star is None else round(q3_rate(delta_star)[1], 3),
                 "plateau": {str(delta_star + k): round(q3_rate(delta_star + k)[0], 3) for k in (-1, 1) if delta_star + k >= 0}
                 if delta_star is not None else {},
                 "recall": "NOT MEASURABLE from this panel, by construction: the stale-NAV gate's record is one-row stale copies (results/cef/LIVE_NAV_QUALITY_2026-10-12.md); a one-row repeat is not a run longer than the name's own trailing maximum, and about a fifth of NAV rows genuinely repeat. The second source (CEFConnect, the decide-time gate) is what separates them."}

    # ---------------------------------------------------------------- Q4
    splits = q.read_splits(data_dir)
    c4_fit = q.q4_candidates(fit["close"], fit["nav"], splits)
    q4_clean = c4_fit.loc[np.array([(t, d) not in exclude for t, d in zip(c4_fit["ticker"], c4_fit["date"])], dtype=bool)]
    rec4 = []
    for t, d in Q4_POS.get(book, []):
        if t not in uni:
            rec4.append({"ticker": t, "date": d, "flagged": False, "why": "not in this book's universe"})
            continue
        day = pd.Timestamp(d)
        win = [day - pd.Timedelta(days=12), day + pd.Timedelta(days=12)]
        hits_none = q.q4_candidates(p.close.loc[win[0]:win[1], [t]], p.nav.loc[win[0]:win[1], [t]], None)
        hits_rows = q.q4_candidates(p.close.loc[win[0]:win[1], [t]], p.nav.loc[win[0]:win[1], [t]], splits)
        rec4.append({"ticker": t, "date": d, "flagged_no_ca_file": hits_none.to_dict("records"),
                     "flagged_with_ca_rows": hits_rows.to_dict("records"),
                     "why": ("the panel has no split-sized step on this name-day (the vendor already split-adjusted it); the "
                             "defect was a recorded split applied again, a formula defect caught by data_guards.guard_split_basis, "
                             "not a panel step" if hits_none.empty else "")})
    out["Q4"] = {"tol": q.SPLIT_TOL, "flags_per_week": round(len(q4_clean) / wk, 3), "n_flags": int(len(q4_clean)),
                 "sample": q4_clean.head(8).assign(date=lambda d: d["date"].astype(str)).to_dict("records"),
                 "recall": rec4}

    # ---------------------------------------------------------------- Q5
    d = q.discounts(fit["close"], fit["nav"])
    keep = pd.DataFrame(True, index=d.index, columns=d.columns)
    if (pd.Timestamp("2021-06-28") in d.index) and ("BME" in d.columns):
        keep.loc[pd.Timestamp("2021-06-28"), "BME"] = False
    def q5_rate(line):
        """Flags as the check emits them: first night past the line (yesterday inside or absent)."""
        past = d.abs() > line
        return float((past & ~past.shift(1, fill_value=False) & keep).sum().sum()) / wk
    line_star = next((float(x) for x in LINE_GRID if q5_rate(x) <= BUDGET), None)
    bme = None
    if "BME" in p.nav.columns and pd.Timestamp("2021-06-28") in p.nav.index:
        bme = float(p.close.loc["2021-06-28", "BME"] / p.nav.loc["2021-06-28", "BME"] - 1)
    bme_flagged = None
    if bme is not None and line_star is not None:
        bme_d = (p.close["BME"] / p.nav["BME"] - 1)
        before = float(bme_d.shift(1).loc["2021-06-28"])
        bme_flagged = bool(abs(bme) > line_star and abs(before) <= line_star)
    out["Q5"] = {"line": line_star, "flags_per_week": None if line_star is None else round(q5_rate(line_star), 3),
                 "plateau": {str(line_star + k): round(q5_rate(line_star + k), 3) for k in (-0.01, 0.01)} if line_star else {},
                 "known_positive_BME_2021_06_28": None if bme is None else round(bme, 4),
                 "recall": bme_flagged,
                 "design_line_50pp_rate": round(q5_rate(0.5), 3)}

    # ---------------------------------------------------------------- Q6
    q6i = fit["close"].index >= Q6_FIT_START
    adv = q.adv_panel(p.close, p.volume).reindex(index=fit["close"].index, columns=p.close.columns)[q6i]
    nav_ok = (fit["nav"].reindex(index=adv.index, columns=adv.columns) > 0)
    floor = float(spec["frozen"]["min_adv_usd"])
    min_names = int(spec["frozen"]["min_names"])
    wk6 = weeks(adv.index)
    n_elig = ((adv >= floor) & nav_ok).sum(axis=1)
    def q6_flags(margin):
        """Nights the sleeve is not yet thin but an ADV dip of `margin` would make it thin."""
        n_safe = ((adv >= floor * (1 + margin)) & nav_ok).sum(axis=1)
        return (n_elig >= min_names) & (n_safe < min_names)
    def q6_rate(margin):
        return float(q6_flags(margin).sum()) / wk6
    # least strict = the largest margin (more nights fire) still within the budget
    margin_star = next((float(m) for m in MARGIN_GRID[::-1] if q6_rate(m) <= BUDGET), None)
    elig = adv.where((adv >= floor) & nav_ok)
    least = (elig / floor).min(axis=1).dropna()
    q6: dict = {"median_least_liquid_eligible_over_floor": round(float(least.median()), 3), "margin": margin_star, "flags_per_week": None if margin_star is None else round(q6_rate(margin_star), 3),
                "plateau": {str(margin_star + k): round(q6_rate(margin_star + k), 3) for k in (-0.005, 0.005)} if margin_star is not None else {},
                "fit_dates_used": [str(adv.index.min().date()), str(adv.index.max().date())]}
    if book == "cef":
        thin = pd.read_csv(THIN, parse_dates=["date"]).set_index("date")
        thin = thin.loc[Q6_FIT_START:FIT_END]
        ep_start = thin.index[(thin["thin"]) & (~thin["thin"].shift(1, fill_value=False))]
        lead = 5
        flagged = q6_flags(margin_star)
        rec6 = []
        for d in ep_start:
            if d not in flagged.index:
                continue
            i = flagged.index.get_loc(d)
            rec6.append({"episode_start": str(d.date()), "flagged_in_prior_5_sessions_or_day": bool(flagged.iloc[max(0, i - lead):i + 1].any())})
        q6["recall_thin_episode_starts"] = rec6
        q6["recall"] = f"{sum(r['flagged_in_prior_5_sessions_or_day'] for r in rec6)}/{len(rec6)}"
    else:
        q6["recall"] = "NOT MEASURABLE: no thin-session record exists for C4 (thin-days-2026-11-03 is the core's)"
    out["Q6"] = q6

    # ---------------------------------------------------------------- budget, jointly
    total = sum(x for x in (out["Q2"]["flags_per_week"], out["Q3"]["new_runs_per_week"], out["Q4"]["flags_per_week"],
                            out["Q5"]["flags_per_week"], out["Q6"]["flags_per_week"]) if x is not None)
    out["joint_flags_per_week_sum_of_shares"] = round(total, 3)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=HERE / "calibration_2026-11-08.json")
    a = ap.parse_args()
    res = {b: run_book(b) for b in ("cef", "c4")}
    res["thresholds"] = {b: {"q2_z": res[b]["Q2"]["z_threshold"], "q3_delta": res[b]["Q3"]["delta"],
                             "q5_line": res[b]["Q5"]["line"], "q6_margin": res[b]["Q6"]["margin"]}
                         for b in ("cef", "c4")}
    a.out.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
