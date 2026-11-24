"""Live turnover vs the live band policy, the deferred-flip cost, and the cost grid.

Report only: zero trials, no spec change. Reproduce from the repo root with

    python3 results/backtests/turnover-live-2026-11-02/turnover_live.py

WHAT THIS ASKS (the parent session's question, 2026-11-02)
---------------------------------------------------------
The live core book traded about 58 turns/yr on Alpaca paper over its first 24
sessions (2026-09-29..10-30; the parent measured it from Alpaca FILL activities,
which this script does not and may not read). Is that in line with what the live
policy trades on the canonical harness? What does the runner's deferred flip
cost? And what does the cost grid, plus the measured 5.5bp paper fill drag, do
to the live policy?

THE HARNESS, UNCHANGED EXCEPT ONE VISIBLE KWARG
----------------------------------------------
* targets  `band_frontier.build_targets()`: the spec's universe, z-window, vol
           target, ADV floor and min_names, all read through scripts/cef/spec.py.
* policy   `band_frontier.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)`:
           the live band then the live ceiling, both read from the spec. The
           harness flips long<->short in one session.
           `defer_flips=True` (added 2026-11-02, tested in
           scripts/cef/tests/test_band_defer_flips.py) is decide.py's
           FLIP_SAME_SESSION=False: the name is held flat for that session.
* returns  `band_frontier.total_returns(R)` (H15): splits + distributions.
* account  `band_frontier.evaluate()`: shift(2) (decide t, fill t+1, earn t+2).
           turn/yr = sum_t sum_i |H[t,i] - H[t-1,i]| x 252 / n; a row's cost is
           turn x bp, taken off the annual return (`band_frontier.row`).

ALIGNMENT (H7): every frame here is a function of `build_targets()`, which is
causal (build_panel's .shift(1) on mu, sd and adv); truncating H and R at a date
after building them is exact. Nothing in this script estimates a parameter.

THE DISTRIBUTION PANEL ENDS BEFORE THE PRICE PANEL (H15)
-------------------------------------------------------
`total_returns` raises when a name has no distribution rows at all, or when an
ex-date in the window fails to land; it does NOT raise when the distribution
panel simply stops before R does, and these 13 funds pay monthly. So every
RETURN statistic below is cut at DIST_END, the last ex-date the panel holds for
any universe name, and the script asserts it. TURNOVER needs no return, so the
turnover-only comparisons with the live record use the full target panel.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from scripts.cef import band_frontier as bf                                # noqa: E402
from scripts.cef.portfolio_baseline import max_drawdown                    # noqa: E402
from scripts.cef.spec import (BAND_WIDTH, MAX_GROSS_STRESS, MIN_ADV_USD,   # noqa: E402
                              MIN_NAMES, UNIVERSE, summary)
from scripts.research.harness import COST_GRID_BP, ERAS, HOLDOUT_START     # noqa: E402
from scripts.research.inference import newey_west_t                        # noqa: E402
from src.deploy.sleeves.cef_discount import _cap_gross                     # noqa: E402

OUT = Path(__file__).resolve().parent
PERIODS = 252

# The live record, as the parent session measured it [V, Alpaca FILL activities
# 2026-09-29..10-30]. Inputs, not outputs of this script; carried so that every
# derived figure names them.
LIVE_TRADED_USD = 558_927.0          # [V parent] sum of |fill notional|
LIVE_SESSIONS = 24                   # [V parent]
LIVE_EQUITY_APPROX = 100_000.0       # [V parent: "about $100k"] -> derived figures are [U]
LIVE_TURN_PARENT = 58.0              # [V parent: "about 58 turns/yr"]
LIVE_FILL_DRAG_BP = 5.5              # [V parent] mean fill vs that day's close, per unit traded
LIVE_FIRST_FILL = pd.Timestamp("2026-09-29")   # [V parent] first session of the window
LIVE_LAST_FILL = pd.Timestamp("2026-10-30")    # [V parent]

# The A2 re-derivation uses the leakage report's window ("traded era",
# PREREG_ALPACA_V7 section 4, as `results/cef/alpha_leakage/code/return_levers/common.py`
# states it), only so that its -0.38pp/yr can be checked like for like.
A2_TRADED_START = "2013-06-14"


def panel_dates() -> dict:
    """Last date of every panel this report reads, for the universe."""
    d = bf.DATA_DIR
    out = {}
    for f, col in (("cef_prices", "date"), ("cef_nav", "date"),
                   ("cef_distributions", "ex_date"), ("cef_splits", "ex_date")):
        x = pd.read_parquet(d / f"{f}.parquet")
        x[col] = pd.to_datetime(x[col])
        u = x[x.ticker.isin(UNIVERSE)] if f != "cef_splits" else x
        out[f] = dict(last_any=str(x[col].max().date()),
                      last_universe=str(u[col].max().date()) if len(u) else None)
    return out


def stats(pnl: pd.Series, turn: pd.Series) -> dict:
    """One row of the report. Gross headline, the 5/15/30bp grid beside it, the
    break-even cost, and the [U] fill-drag arithmetic. Formulas are
    `band_frontier.row`'s: net = (ann - turn x bp/1e4) / vol."""
    ann, vol = pnl.mean() * PERIODS, pnl.std() * np.sqrt(PERIODS)
    t = turn.mean() * PERIODS
    if vol == 0.0:
        # A window in which the book never held anything (2005-09: the 13-name
        # universe never has min_names eligible). There is no Sharpe to report,
        # and a NaN in a table reads as a failure; say what it is instead.
        if ann != 0.0 or t != 0.0:
            raise AssertionError("zero vol with a non-zero return or turnover")
        return dict(start=str(pnl.index[0].date()), end=str(pnl.index[-1].date()), n=len(pnl),
                    flat=True, ann=0.0, vol=0.0, turn=0.0, mdd=0.0)
    nets = {c: (ann - t * c / 1e4) / vol for c in COST_GRID_BP}
    net_ann = {c: ann - t * c / 1e4 for c in COST_GRID_BP}
    return dict(start=str(pnl.index[0].date()), end=str(pnl.index[-1].date()), n=len(pnl), flat=False,
                gross_sr=ann / vol, ann=ann, vol=vol, mdd=max_drawdown(pnl)["mdd"], turn=t,
                net_sr=nets, net_ann=net_ann,
                breakeven_bp=(ann / t * 1e4) if t > 0 else np.inf,
                flips_sign=len({np.sign(v) for v in nets.values()}) > 1,
                drag_pp=t * LIVE_FILL_DRAG_BP / 1e4)


def windows(index: pd.DatetimeIndex, end: pd.Timestamp) -> list:
    """H5 eras, then the fit row and the H13 row, then the full sample."""
    w = [(lab, pd.Timestamp(a), pd.Timestamp(b) if b else end) for lab, a, b in ERAS]
    w += [("FIT <2023", index[0], HOLDOUT_START - pd.Timedelta(days=1)),
          ("H13 2023+", HOLDOUT_START, end),
          ("full", index[0], end)]
    return w


def table(H: pd.DataFrame, R: pd.DataFrame, end: pd.Timestamp) -> dict:
    r = bf.evaluate(H, R)
    pnl, turn = r["pnl"], r["turn_series"]
    out = {}
    for lab, a, b in windows(pnl.index, end):
        m = (pnl.index >= a) & (pnl.index <= b)
        if m.sum() >= 2:
            out[lab] = stats(pnl[m], turn[m])
    return out


def fmt_table(rows: dict, title: str) -> str:
    hdr = (f"{'window':<11}{'dates':<24}{'grossSR':>8}{'ann%':>7}{'vol%':>6}{'maxDD%':>8}{'turn/yr':>8}"
           f" |{'net@5':>7}{'net@15':>7}{'net@30':>7}{'flip?':>6} |{'n%@5':>6}{'n%@15':>6}{'n%@30':>6}"
           f"{'BEbp':>6} |{'drag%[U]':>9}")
    lines = [title, hdr, "-" * len(hdr)]
    for lab, s in rows.items():
        if s["flat"]:
            lines.append(f"{lab:<11}{s['start'] + '..' + s['end']:<24}  FLAT: the book held nothing "
                         f"(fewer than min_names eligible on every session; harness holds the empty book)")
            continue
        lines.append(
            f"{lab:<11}{s['start'] + '..' + s['end']:<24}{s['gross_sr']:8.2f}{s['ann'] * 100:7.2f}"
            f"{s['vol'] * 100:6.2f}{-s['mdd'] * 100:8.1f}{s['turn']:8.1f}"
            f" |{s['net_sr'][5]:7.2f}{s['net_sr'][15]:7.2f}{s['net_sr'][30]:7.2f}"
            f"{('YES' if s['flips_sign'] else 'no'):>6} |{s['net_ann'][5] * 100:6.2f}"
            f"{s['net_ann'][15] * 100:6.2f}{s['net_ann'][30] * 100:6.2f}{s['breakeven_bp']:6.1f}"
            f" |{s['drag_pp'] * 100:9.2f}")
    return "\n".join(lines)


def flips_per_year(H: pd.DataFrame, a, b) -> float:
    """Name-sessions on which the held book goes long<->short in one session."""
    f = ((H.shift(1).fillna(0.0) * H) < 0).sum(axis=1)
    m = (H.index >= a) & (H.index <= b)
    return float(f[m].sum() * PERIODS / m.sum())


def main() -> dict:
    res: dict = {"spec": summary(), "panels": panel_dates()}
    print(summary())
    print("panels:", json.dumps(res["panels"]))

    T, R_px = bf.build_targets()
    T_END = T.index[-1]
    dist = pd.read_parquet(bf.DATA_DIR / "cef_distributions.parquet")
    dist["ex_date"] = pd.to_datetime(dist["ex_date"])
    DIST_END = dist.loc[dist.ticker.isin(UNIVERSE), "ex_date"].max()
    if DIST_END >= T_END:
        raise AssertionError("distribution panel reaches the target panel; revisit the cut")
    keep = T.index <= DIST_END
    R_tr = bf.total_returns(R_px.loc[keep])
    assert R_tr.index.max() <= DIST_END, "a return past the distribution panel's coverage"
    res.update(T_start=str(T.index[0].date()), T_end=str(T_END.date()), DIST_END=str(DIST_END.date()))
    print(f"targets {T.index[0].date()}..{T_END.date()}; total returns cut at DIST_END {DIST_END.date()}")

    # ---- the two books --------------------------------------------------------------
    H_inst = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)                    # harness: flip in one session
    H_def = bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS, defer_flips=True)    # live runner: deferred flip
    Hi, Hd = H_inst.loc[keep], H_def.loc[keep]

    # ---- (1) + (3): the live policy, by era, gross headline with the grid beside it ---
    ti = table(Hi, R_tr, DIST_END)
    td = table(Hd, R_tr, DIST_END)
    res["live_policy_instant_flip"] = ti
    res["live_policy_deferred_flip"] = td
    note = (f"TOTAL returns; gross headline; net@bp = (ann - turn x bp)/vol, labelled real-money view; "
            f"n%@bp = net ann %; BEbp = ann/turn; drag%[U] = turn x {LIVE_FILL_DRAG_BP}bp (paper fill drag, "
            f"arithmetic only). No borrow charged. maxDD compounded. Return panel end {DIST_END.date()}.")
    print("\n" + fmt_table(ti, f"[A] LIVE POLICY {bf._lab_band(BAND_WIDTH).strip()} + cap {MAX_GROSS_STRESS}x, "
                               "harness (flip in one session)"))
    print(note)
    print("\n" + fmt_table(td, "[B] LIVE POLICY with the runner's DEFERRED FLIP (defer_flips=True)"))

    # H5 sd/mean over the eras, all five (a flat era trades 0/yr, which is what it did)
    era_turn = [ti[e[0]]["turn"] for e in ERAS if e[0] in ti]
    era_turn_d = [td[e[0]]["turn"] for e in ERAS if e[0] in td]
    era_turn_x = [ti[e[0]]["turn"] for e in ERAS if e[0] in ti and not ti[e[0]]["flat"]]
    res["era_turn_cv_instant_excl_flat"] = float(np.std(era_turn_x, ddof=1) / np.mean(era_turn_x))
    res["era_turn_cv_instant"] = float(np.std(era_turn, ddof=1) / np.mean(era_turn))
    res["era_turn_cv_deferred"] = float(np.std(era_turn_d, ddof=1) / np.mean(era_turn_d))
    print(f"H5 era turnover sd/mean (ddof=1): instant {res['era_turn_cv_instant']:.1%}, "
          f"deferred {res['era_turn_cv_deferred']:.1%}; instant excluding the flat era "
          f"{res['era_turn_cv_instant_excl_flat']:.1%}")

    # ---- thin cross-section: sessions under min_names (the harness HOLDS, the live sleeve FLATTENS) ---
    p = bf.build_panel()
    z, adv = p["z"].reindex(T.index), p["adv"].reindex(T.index)
    elig = (z.notna() & (adv >= MIN_ADV_USD)).sum(axis=1)
    thin = (elig < MIN_NAMES)
    res["thin_sessions"] = {lab: int(thin[(thin.index >= a) & (thin.index <= (b or T_END))].sum())
                            for lab, a, b in [(e[0], e[1], e[2]) for e in ERAS]}
    res["thin_sessions_live_window"] = int(thin.loc["2026-09-28":].sum())
    print("sessions with < min_names eligible (harness holds; live sleeve flattens):", res["thin_sessions"],
          "| decisions 2026-09-28..:", res["thin_sessions_live_window"])

    # ---- where the recent era's turnover comes from: days the ceiling binds -------------
    # `_cap_gross` scales the WHOLE held book when gross > cap, so on a binding day every
    # held name trades (cef_discount.py: "THE BAND'S HOLDS BECOME TRADES WHEN THIS BINDS").
    # Descriptive decomposition of the instant book's turnover, nothing estimated.
    gross_h = H_inst.abs().sum(axis=1)
    binds = gross_h >= MAX_GROSS_STRESS - 1e-9
    dec = {}
    print("\n[B2] TURNOVER ON DAYS THE GROSS CEILING BINDS (instant book, decision rows, to T_END)")
    print(f"{'window':<11}{'turn/yr':>8}{'bind days %':>12}{'turn/yr on bind days':>22}{'share':>7}{'flip turn/yr':>13}")
    flip_turn = (H_inst.diff().abs().where((H_inst.shift(1) * H_inst) < 0, 0.0)).sum(axis=1)
    for lab, a, b in windows(T.index, T_END):
        m = (T.index >= a) & (T.index <= b)
        tt = H_inst.diff().abs().sum(axis=1).fillna(0.0)[m]
        n = m.sum()
        d = dict(turn=float(tt.sum() * PERIODS / n), bind_share=float(binds[m].mean()),
                 turn_on_bind=float(tt[binds[m]].sum() * PERIODS / n),
                 flip_turn=float(flip_turn[m].sum() * PERIODS / n))
        d["share"] = d["turn_on_bind"] / d["turn"] if d["turn"] > 0 else float("nan")
        dec[lab] = d
        print(f"{lab:<11}{d['turn']:8.1f}{d['bind_share'] * 100:12.1f}{d['turn_on_bind']:22.1f}"
              f"{d['share'] * 100 if d['turn'] > 0 else float('nan'):7.1f}{d['flip_turn']:13.1f}")
    res["turnover_decomposition"] = dec

    # ---- (2): the deferred flip against flipping in one session ----------------------
    r_i, r_d = bf.evaluate(Hi, R_tr), bf.evaluate(Hd, R_tr)
    diff = r_d["pnl"] - r_i["pnl"]
    fl_rows = []
    wins = windows(Hi.index, DIST_END) + [("A2 traded", pd.Timestamp(A2_TRADED_START), DIST_END)]
    print("\n[C] DEFERRED FLIP minus FLIP-IN-ONE-SESSION (TOTAL returns; difference = deferred - instant)")
    hdr = (f"{'window':<11}{'flips/yr':>9}{'SR inst':>8}{'SR def':>8}{'d ann pp':>9}{'NW t':>6}"
           f"{'turn inst':>10}{'turn def':>9}{'d turn':>8} |{'d net pp@5':>11}{'@15':>7}{'@30':>7}")
    print(hdr); print("-" * len(hdr))
    for lab, a, b in wins:
        m = (diff.index >= a) & (diff.index <= b)
        si = stats(r_i["pnl"][m], r_i["turn_series"][m])
        sd = stats(r_d["pnl"][m], r_d["turn_series"][m])
        if si["flat"] and sd["flat"]:
            print(f"{lab:<11}  both books FLAT in this window: no difference to measure")
            fl_rows.append(dict(window=lab, flat=True))
            continue
        dpp = (sd["ann"] - si["ann"]) * 100
        dnet = {c: (sd["net_ann"][c] - si["net_ann"][c]) * 100 for c in COST_GRID_BP}
        nwt = newey_west_t(diff[m].to_numpy())
        row = dict(window=lab, start=si["start"], end=si["end"], flips_per_yr=flips_per_year(Hi, a, b),
                   sr_inst=si["gross_sr"], sr_def=sd["gross_sr"], d_ann_pp=dpp, nw_t=nwt,
                   turn_inst=si["turn"], turn_def=sd["turn"], d_turn=sd["turn"] - si["turn"], d_net_pp=dnet)
        fl_rows.append(row)
        print(f"{lab:<11}{row['flips_per_yr']:9.1f}{row['sr_inst']:8.2f}{row['sr_def']:8.2f}{dpp:9.2f}{nwt:6.2f}"
              f"{row['turn_inst']:10.1f}{row['turn_def']:9.1f}{row['d_turn']:8.1f} |"
              f"{dnet[5]:11.2f}{dnet[15]:7.2f}{dnet[30]:7.2f}")
    res["deferred_flip"] = fl_rows

    # ---- (1) continued: is ~58/yr in line with the policy's recent turnover? -------------
    # Turnover needs no return, so these use the FULL target panel (to T_END).
    ts_i = H_inst.diff().abs().sum(axis=1).fillna(0.0)
    ts_d = H_def.diff().abs().sum(axis=1).fillna(0.0)
    cmp = {}
    for lab, ts in (("instant", ts_i), ("deferred", ts_d)):
        c = {}
        c["2023+ to T_END"] = float(ts.loc["2023":].mean() * PERIODS)
        c["last 252 decisions"] = float(ts.iloc[-252:].mean() * PERIODS)
        c["last 63 decisions"] = float(ts.iloc[-63:].mean() * PERIODS)
        # the live window's decisions: a fill on s is decided on the session before s
        win = ts.loc[T.index[T.index.get_indexer([LIVE_FIRST_FILL], method="bfill")[0] - 1]:]
        c["decisions 2026-09-28..T_END"] = float(win.mean() * PERIODS)
        c["decisions 2026-09-28..T_END n"] = int(len(win))
        c["decisions 2026-09-28..T_END first"] = str(win.index[0].date())
        roll = ts.loc["2023":].rolling(LIVE_SESSIONS).mean().dropna() * PERIODS
        c["rolling24 2023+ p05/p50/p95/max"] = [float(roll.quantile(q)) for q in (0.05, 0.5, 0.95)] + [float(roll.max())]
        c["rolling24 2023+ share >= 58"] = float((roll >= LIVE_TURN_PARENT).mean())
        cmp[lab] = c
    # The live book OPENED from flat to FULL TARGET (cef_discount.py "OPENING SESSION";
    # the ceiling still applies). Its build is one-off turnover the harness, which has
    # been invested since 2005, never pays in this window. Size it on the harness
    # target for the opening decision (the session before the first fill).
    d0 = T.index[T.index.get_indexer([LIVE_FIRST_FILL], method="bfill")[0] - 1]
    open_book, f = _cap_gross(T.loc[d0], MAX_GROSS_STRESS)
    build = float(open_book.abs().sum())
    live_turns_window = LIVE_TRADED_USD / LIVE_EQUITY_APPROX
    cmp["opening"] = dict(decision=str(d0.date()), target_gross_uncapped=float(T.loc[d0].abs().sum()),
                          cap_scale=float(f), build_turns=build,
                          live_turns_in_window_U=live_turns_window,
                          live_turn_yr_U=live_turns_window * PERIODS / LIVE_SESSIONS,
                          live_turn_yr_ex_build_U=(live_turns_window - build) * PERIODS / LIVE_SESSIONS,
                          build_share_U=build / live_turns_window)
    res["live_comparison"] = cmp
    print("\n[D] TURNOVER: live record vs the live policy on the harness (turn/yr)")
    for lab in ("instant", "deferred"):
        print(f"  harness {lab:<9}", json.dumps({k: (round(v, 1) if isinstance(v, float) else
                                                    [round(x, 1) for x in v] if isinstance(v, list) else v)
                                                for k, v in cmp[lab].items()}))
    print("  opening build", json.dumps({k: (round(v, 3) if isinstance(v, float) else v)
                                         for k, v in cmp["opening"].items()}))

    # ---- context only: the frontier's other widths, same cap, nothing chosen --------------
    ctx = {}
    print("\n[E] CONTEXT ONLY (frontier widths, BAND_SWEEP, same ceiling; nothing is chosen from this)")
    print(f"{'width':<16}{'FIT SR':>8}{'FIT turn':>9}{'H13 SR':>8}{'H13 turn':>9}{'2023+ turn to T_END':>21}")
    for b in bf.BAND_SWEEP:
        Hb = bf.band_gross_capped(T, b, MAX_GROSS_STRESS)
        tb = table(Hb.loc[keep], R_tr, DIST_END)
        t_all = float(Hb.diff().abs().sum(axis=1).loc["2023":].mean() * PERIODS)
        ctx[f"{b:.3f}"] = dict(fit_sr=tb["FIT <2023"]["gross_sr"], fit_turn=tb["FIT <2023"]["turn"],
                               h13_sr=tb["H13 2023+"]["gross_sr"], h13_turn=tb["H13 2023+"]["turn"],
                               turn_2023_to_T_END=t_all)
        print(f"{bf._lab_band(b):<16}{tb['FIT <2023']['gross_sr']:8.2f}{tb['FIT <2023']['turn']:9.1f}"
              f"{tb['H13 2023+']['gross_sr']:8.2f}{tb['H13 2023+']['turn']:9.1f}{t_all:21.1f}")
    res["context_widths"] = ctx

    (OUT / "results.json").write_text(json.dumps(res, indent=1, default=str))
    print(f"\nwrote {OUT / 'results.json'}")
    return res


if __name__ == "__main__":
    main()
