"""EVENTS trial 3, part (b): the opening (prereg §9.1) and its rehearsal on fit data.

    python3 scripts/events/exdrift_trial.py rehearse                         # fit 2021-01-01..2022-12-30 only
    python3 scripts/events/exdrift_trial.py open --team-lead-go YYYY-MM-DD   # THE ONE OPENING (never run by an agent)

WHAT THIS IS
------------
This is the evaluator of `results/events/PREREG_EXDATE_DRIFT_2026-10-26.md`. It was written after
Stage 0 cleared, and then reviewed independently (quant review of 2026-10-28; its findings are
fixed here and listed in `results/events/EXDRIFT_STAGE0_2026-10-27.md`). It covers:
- §4.5, the evaluator: legs into `band_frontier.event_hold`, then `evaluate`, `_cap_gross` and
  `borrow_charge`;
- §4.6, the controls: the placebo calendar at +5 and −10, pooled, and the NAV leg;
- §9.1, the kill order, stages 1–6, with the verdict as the first failing rule;
- §5.4, the eras;
- §6, costs and borrow, beside and labelled, deciding nothing.

AMENDMENT 1 (the MUB/IEF hedge) was WITHDRAWN by the team lead on 2026-10-28. `load_test` runs the
ORIGINAL design and never sets `hedge_betas`. The hedge code remains only so that the record's
rehearsals of the amendment can be reproduced (`rehearse --hedge`, `fit-d4`).

`open_core` takes an `OpenData` and reads no file. The same code runs on the test set and on the
rehearsal:
- `load_test` serves the test set. It needs the gate's token from `exdrift_trial.open_gate`.
- `load_rehearsal` serves fit rows only (2021–22), as C4 rehearsed.

HALT, NOT KILL. The rules raise `OpenError` on a missing input instead of failing a stage; §9.1
stage 0 says a data failure is a HALT. They raise on:
- a factor gap in the P&L window;
- an empty control;
- a declaration that cannot be read at a leg;
- an ex-date that is not a session.

DEFINITIONS (prereg §4; readings O1–O4 are in `exdrift_trial.OPEN_READINGS`, ruled by the team lead
before `open`):
- **An event (i, e)** is eligible when all five rules hold:
  1. declared on or before e-1 (R4);
  2. no other own ex-date in (e, e+3];
  3. not split-masked (r6's ±5-session mask on the splits panel, R1);
  4. a finite return on each of e+1..e+3;
  5. an H-E basket of at least 3.
- **The H-E basket** is the other funds with no own ex-date in [e+1, e+8] declared by e-1, and a
  finite return on each of e+1..e+3. Under R10 (KEEP) an ex-date with no declaration found stays
  in, and `unknown="exclude"` is computed beside it.
- **The per-event P&L** is x_e = -sum over k=1..3 of (r_i - mean of the basket's r), on price total
  returns. Positive means the drift paid the short.
- **The raw sleeve** is $1 short and $1 basket per event, decided on rows e-1, e and e+1. It is
  `event_hold`, then `evaluate`, asserted equal to the sum of the per-event P&Ls.
- **The tradable sleeve** is k (fit-k) times the raw sleeve, capped row by row at
  `spec.MAX_GROSS_STRESS`.
- **The P&L window (O1)** runs from the first session on or after 2023-01-01 to the frozen end's
  cover row (§5.1). For the test that is T = 950 sessions, the T of §10.
- **R-D4's betas "at the vol target" (O2)**: the summed betas times VOL_TARGET / sigma(tradable
  sleeve over the window). That is the NAV-tender precedent, whose sizing rule §4.4 copies.
- **Stage 3 (O3)** compares the NAV-leg mean with the price-leg mean on the same events (those
  with a NAV leg after the X5 exclusions). The full-set comparison is printed beside.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("compute.use_numexpr", False)          # DG-X8

REPO = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------- the declared rules (prereg §9.1)
T_BAR = 2.0                    # stage 1: month-clustered t >= 2.0 and mean > 0
CONTROL_FRACTION = 0.5         # stages 2, 3: a control at >= 1/2 the real mean, same sign, kills
ALPHA_T_BAR, BETA_MAX = 3.0, 0.10    # stage 5
DSR_PASS = 0.95                # stage 6
NW_LAGS = 21
GRID_BP = (5, 15, 30)
PLACEBO_SHIFTS = (5, -10)      # pooled; +10 is report-only
PLACEBO_REPORT = (10,)
PLACEBO_CLEAR = 3              # a placebo hold row within [-3, +3] of a real own ex-date drops the placebo event
HOLD, HE_LO, HE_HI, BASKET_MIN, NEXT_EX_WITHIN = 3, 1, 8, 3, 3
BOOT_REPS, SEED = 10_000, 20261027
CAPITALS = (1e5, 1e6, 1e7)
X4_BASIS_TOL_USD = 0.01        # Alpaca vs yfinance close on one session: C4's adjacent-bar check (2026-10-14)
LIMITATION_R10 = ("Stated limitation (team lead's ruling R10, 2026-10-28: KEEP): a basket fund whose ex-date in "
                  "[e+1, e+8] has no declaration found stays in the basket, so the hedge basket's exclusion window "
                  "uses ex-dates that may not have been public at decide time.")
_GATE_TOKEN = object()         # handed out only by exdrift_trial.open_gate


class OpenError(RuntimeError):
    """An input the opening cannot use as it is: a HALT, named, never filled and never a kill."""


@dataclass
class OpenData:
    label: str
    sessions: pd.DatetimeIndex           # the position calendar
    R: pd.DataFrame                      # price total returns (masked as r6 masks), sessions x the 17
    Rpx: pd.DataFrame                    # price-only returns, same masks
    RN: pd.DataFrame                     # NAV total returns, same masks
    masked: pd.DataFrame                 # True where r6's split mask removed the return (rule 3)
    exdates: pd.DataFrame                # every ex-date: ticker, ex_date, declared (NaT = none found), amount, amount_strata, special
    candidates: pd.DataFrame             # the window's event candidates: ticker, ex_date
    nav_excluded: set                    # (ticker, ex_date) out of the NAV leg (X5 rulings)
    close_prev: pd.DataFrame             # raw close levels (for yields and capacity), sessions x the 17
    adv63: pd.DataFrame                  # 63-session mean dollar volume ending at each row
    factors: pd.DataFrame                # mktrf smb hml rmw cma umd TERM HY MUNI, on the sessions
    fee_pct: pd.DataFrame | None         # B-meas borrow fee, % per year
    hyg: pd.Series | None                # HYG total return (the report-only $1-for-$1 hedge)
    k: float
    cap: float
    vol_target: float
    n_bar: int
    window: tuple                        # (first, last) session of the P&L series (O1)
    eras: list
    core13: tuple
    munis: tuple
    rich_cheap: pd.DataFrame | None = None
    shortable_today: dict = field(default_factory=dict)
    regime_split: pd.Timestamp | None = None
    unknown_mode: str = "keep"           # R10
    hedge_betas: dict | None = None      # amendment 1: frozen fit betas {ticker: {beta_MUB, beta_IEF}}
    hedge_R: pd.DataFrame | None = None  # amendment 1: MUB and IEF total returns on the sessions
    notes: list = field(default_factory=list)


# --------------------------------------------------------------------------- events and baskets

def _pos(sessions):
    return {d: i for i, d in enumerate(sessions)}


def own_declared(D: OpenData) -> dict:
    sp = _pos(D.sessions)
    out: dict = {}
    for t, x, dd in zip(D.exdates.ticker, D.exdates.ex_date, D.exdates.declared):
        if x not in sp:
            raise OpenError(f"{t} ex-date {pd.Timestamp(x).date()} is not a session (H15: raise, never drop)")
        out.setdefault(t, []).append((sp[x], dd))
    return out


def own_ex_positions(D: OpenData) -> dict:
    return {t: sorted(q for q, _ in v) for t, v in own_declared(D).items()}


def basket_for(D: OpenData, t: str, p: int, own_decl: dict, unknown: str = "keep") -> list[str] | None:
    """H-E for (t, position p). A fund leaves if it has an ex-date in [p+1, p+8] declared by p-1.
    `unknown="keep"` (R10) keeps a fund whose in-window ex-date has no declaration found;
    `"exclude"` drops it (the beside row)."""
    cutoff = D.sessions[p - 1]
    rows = [p + 1, p + 2, p + 3]
    out = []
    for j in D.R.columns:
        if j == t:
            continue
        inwin = [dd for q, dd in own_decl.get(j, []) if HE_LO <= q - p <= HE_HI]
        if any(pd.notna(dd) and dd <= cutoff for dd in inwin):
            continue
        if unknown == "exclude" and any(pd.isna(dd) for dd in inwin):
            continue
        if not np.isfinite(D.R[j].to_numpy()[rows]).all():
            continue
        out.append(j)
    return out if len(out) >= BASKET_MIN else None


def build_events(D: OpenData, shift: int = 0, real: pd.DataFrame | None = None,
                 unknown: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Eligible events (shift 0), or placebo events at e + shift for the events of `real`.

    A placebo event takes the same rules relative to its placebo date, and survives only if none of
    its hold rows is within [-3, +3] of a real own ex-date of the fund (prereg §4.6)."""
    unknown = unknown or D.unknown_mode
    sp = _pos(D.sessions)
    decl = own_declared(D)
    ownx = {t: [q for q, _ in v] for t, v in decl.items()}
    dmin = D.exdates.groupby(["ticker", "ex_date"]).declared.min()
    n = {"candidates": 0, "rule1_not_declared": 0, "rule2_next_ex": 0, "rule3_split_mask": 0, "rule4_no_return": 0,
         "rule5_basket_lt3": 0, "placebo_near_real_ex": 0, "outside_window": 0}
    base = D.candidates if real is None else real
    rows = []
    for r in base.itertuples():
        if r.ex_date not in sp:
            raise OpenError(f"{r.ticker} ex-date {r.ex_date.date()} is not a session")
        p = sp[r.ex_date] + shift
        n["candidates"] += 1
        if p - 2 < 0 or p + HOLD >= len(D.sessions) or not (
                D.window[0] <= D.sessions[p + 1] and D.sessions[p + HOLD] <= D.window[1]):
            n["outside_window"] += 1
            continue
        hold = [p + 1, p + 2, p + 3]
        if shift == 0:
            dd = dmin.get((r.ticker, r.ex_date), pd.NaT)
            if pd.isna(dd) or dd > D.sessions[p - 1]:
                n["rule1_not_declared"] += 1
                continue
            if any(p < q <= p + NEXT_EX_WITHIN for q in ownx.get(r.ticker, [])):
                n["rule2_next_ex"] += 1
                continue
        elif any(abs(h - q) <= PLACEBO_CLEAR for q in ownx.get(r.ticker, []) for h in hold):
            n["placebo_near_real_ex"] += 1
            continue
        if D.masked[r.ticker].to_numpy()[hold].any():
            n["rule3_split_mask"] += 1
            continue
        ri = D.R[r.ticker].to_numpy()[hold]
        if not np.isfinite(ri).all():
            n["rule4_no_return"] += 1
            continue
        b = basket_for(D, r.ticker, p, decl, unknown)
        if b is None:
            n["rule5_basket_lt3"] += 1
            continue
        bm = D.R[b].to_numpy()[hold].mean(axis=1)
        x_un = float(-(ri - bm).sum())
        hM = hI = 0.0
        x = x_un
        if D.hedge_betas is not None:                       # amendment 1: the event's MUB and IEF hedge
            from scripts.events.exdrift_trial import hedge_weights
            hM, hI = hedge_weights(r.ticker, b, D.hedge_betas)
            hr = D.hedge_R[["MUB", "IEF"]].to_numpy()[hold]
            if not np.isfinite(hr).all():
                raise OpenError(f"amendment 1: no MUB or IEF return on a hold row of {r.ticker} {r.ex_date.date()}: HALT")
            x = x_un + float((hr @ np.array([hM, hI])).sum())
        x_px = float(-(D.Rpx[r.ticker].to_numpy()[hold] - D.Rpx[b].to_numpy()[hold].mean(axis=1)).sum())
        a = D.RN[r.ticker].to_numpy()[hold]
        bn = D.RN[b].to_numpy()[hold]
        excl = (r.ticker, r.ex_date) in D.nav_excluded
        nav_ok = (not excl) and np.isfinite(a).all() and (np.isfinite(bn).sum(axis=1) >= BASKET_MIN).all()
        x_nav = float(-(a - np.nanmean(bn, axis=1)).sum()) if nav_ok else np.nan
        hyg = D.hyg.to_numpy()[hold] if D.hyg is not None else None
        x_hyg = float(-(ri - hyg).sum()) if hyg is not None and np.isfinite(hyg).all() else np.nan
        x_hd = float(-(ri - np.nanmean(D.R.to_numpy()[hold], axis=1)).sum())
        surprise = int(np.sum(~np.isclose(D.R[b].to_numpy()[hold], D.Rpx[b].to_numpy()[hold], rtol=0, atol=1e-12)))
        rows.append(dict(ticker=r.ticker, ex_date=r.ex_date, p=p, decision=D.sessions[p - 1], basket=",".join(b),
                         nb=len(b), x=x, x_unhedged=x_un, h_MUB=hM, h_IEF=hI, x_px=x_px, x_nav=x_nav,
                         nav_ruled_out=excl, x_hyg=x_hyg, x_hd=x_hd, surprise_cells=surprise))
    return pd.DataFrame(rows), n


# --------------------------------------------------------------------------- statistics

def month_t(df: pd.DataFrame, col: str) -> dict:
    g = df.dropna(subset=[col]) if len(df) else df
    if not len(g):
        return {"events": 0, "mean_bp": float("nan"), "months": 0, "t_month": float("nan")}
    m = g.groupby(pd.to_datetime(g.ex_date).dt.to_period("M"))[col].mean()
    t = float(m.mean() / m.std(ddof=1) * math.sqrt(len(m))) if len(m) > 1 and m.std(ddof=1) > 0 else float("nan")
    return {"events": int(len(g)), "mean_bp": float(1e4 * g[col].mean()), "months": int(len(m)), "t_month": t}


def date_t(df: pd.DataFrame, col: str) -> float:
    g = df.dropna(subset=[col])
    m = g.groupby("ex_date")[col].mean()
    return float(m.mean() / m.std(ddof=1) * math.sqrt(len(m))) if len(m) > 1 else float("nan")


def month_boot(df: pd.DataFrame, col: str, reps: int = BOOT_REPS, seed: int = SEED) -> dict:
    """Months resampled with replacement; the event mean of each draw. P(mean <= 0) and a 95% band."""
    g = df.dropna(subset=[col])
    groups = [v.to_numpy() for _, v in g.groupby(pd.to_datetime(g.ex_date).dt.to_period("M"))[col]]
    if len(groups) < 2:
        raise OpenError(f"the bootstrap of {col} has fewer than 2 months")
    rng = np.random.default_rng(seed)
    sums, cnts = np.array([v.sum() for v in groups]), np.array([len(v) for v in groups])
    idx = rng.integers(0, len(groups), size=(reps, len(groups)))
    means = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    return {"p_le_0": float((means <= 0).mean()), "lo_bp": float(1e4 * np.quantile(means, 0.025)),
            "hi_bp": float(1e4 * np.quantile(means, 0.975))}


def control_kills(ctrl_mean: float, real_mean: float) -> bool:
    """§9.1 stages 2-3: the control kills at >= 1/2 the real mean with the same sign. A control that
    cannot be measured is a HALT (raise), never a pass (review S3; e1's rule)."""
    if not (np.isfinite(ctrl_mean) and np.isfinite(real_mean)):
        raise OpenError(f"a control cannot be measured (control {ctrl_mean}, real {real_mean}): HALT")
    if real_mean == 0:
        return False
    return bool(np.sign(ctrl_mean) == np.sign(real_mean) and abs(ctrl_mean) >= CONTROL_FRACTION * abs(real_mean))


def dimson_d4(pnl: pd.Series, F: pd.DataFrame, scale: float) -> dict:
    """Stage 5: OLS of the tradable sleeve's daily gross P&L on each factor at t and t-1, HAC(21);
    betas summed and multiplied by `scale` = VOL_TARGET / sigma(sleeve) (O2). A session without every
    factor (including the t-1 row of the first) raises: that is a HALT (§9.1 stage 0), not a kill."""
    import statsmodels.api as sm
    cols = list(F.columns)
    Z = pd.concat([F[cols].reindex(pnl.index), F[cols].shift(1).reindex(pnl.index).add_suffix("_l1")], axis=1)
    d = pd.concat([pnl.rename("y"), Z], axis=1)
    miss = d.index[d.isna().any(axis=1)]
    if len(miss):
        raise OpenError(f"R-D4: {len(miss)} P&L session(s) without every factor (first {miss[0].date()}): HALT")
    f = sm.OLS(d["y"], sm.add_constant(d.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS})
    raw = {c: float(f.params[c] + f.params[c + "_l1"]) for c in cols}
    at = {c: v * scale for c, v in raw.items()}
    se = {}
    for c in cols:                                    # report-only: the HAC standard error of each summed beta
        R_ = np.zeros(len(f.params))
        R_[list(f.params.index).index(c)] = 1.0
        R_[list(f.params.index).index(c + "_l1")] = 1.0
        se[c] = float(np.sqrt(R_ @ f.cov_params().to_numpy() @ R_) * scale)
    return {"n": int(len(d)), "alpha_ann": float(f.params["const"] * 252), "alpha_t": float(f.tvalues["const"]),
            "scale_to_vol_target": scale, "betas_summed_raw": raw, "betas_summed_at_target": at,
            "max_abs_beta_at_target": float(max(abs(v) for v in at.values())),
            "max_abs_beta_raw": float(max(abs(v) for v in raw.values())), "se_at_target_report_only": se,
            "pass": bool(f.tvalues["const"] >= ALPHA_T_BAR and all(abs(v) <= BETA_MAX for v in at.values()))}


def dsr(pnl: pd.Series, n_bar: int) -> dict:
    from scripts.cef.validate import _dsr
    sr = float(pnl.mean() / pnl.std(ddof=1) * math.sqrt(252))
    sk, ku = float(pnl.skew()), float(pnl.kurt() + 3.0)
    d, sr0, emax = _dsr(sr, len(pnl), sk, ku, n_bar)
    return {"sr": sr, "T": int(len(pnl)), "skew": sk, "kurt": ku, "N": n_bar, "dsr": float(d), "sr0": float(sr0),
            "e_max": float(emax), "pass": bool(d > DSR_PASS)}


# --------------------------------------------------------------------------- the sleeve

def sleeve(D: OpenData, ev: pd.DataFrame) -> dict:
    """Raw H (event_hold) -> evaluate (shift 2); k x H capped row by row; borrow; the grid."""
    from scripts.cef.band_frontier import _stats, borrow_charge, evaluate, event_hold
    from src.deploy.sleeves.cef_discount import _cap_gross
    idx = D.sessions
    dmin = D.exdates.groupby(["ticker", "ex_date"]).declared.min()
    legs = []
    for r in ev.itertuples():
        f0, l0 = idx[r.p - 1], idx[r.p + 1]
        ann = dmin.get((r.ticker, r.ex_date), pd.NaT)
        if pd.isna(ann):
            raise OpenError(f"{r.ticker} {r.ex_date.date()}: a traded event without a declaration date")
        legs.append(dict(permno=r.ticker, first=f0, last=l0, weight=-1.0, ann=ann))   # event_hold asserts fill > ann
        b = r.basket.split(",")
        for j in b:
            legs.append(dict(permno=j, first=f0, last=l0, weight=1.0 / len(b), ann=ann))
        if D.hedge_betas is not None:                          # amendment 1: the event's hedge legs, same rows
            for sym, w in (("MUB", r.h_MUB), ("IEF", r.h_IEF)):
                if w != 0.0:
                    legs.append(dict(permno=sym, first=f0, last=l0, weight=float(w), ann=ann))
    H = event_hold(pd.DataFrame(legs), idx)
    RA = D.R if D.hedge_R is None else pd.concat([D.R, D.hedge_R[["MUB", "IEF"]]], axis=1)
    R = RA.reindex(columns=H.columns)
    held = H.shift(2).fillna(0.0).to_numpy() != 0
    if not np.isfinite(R.to_numpy()[held]).all():
        raise OpenError("a held cell has no return: evaluate() would book it as 0")
    raw = evaluate(H, R.fillna(0.0))        # held cells asserted finite just above
    win = (idx >= D.window[0]) & (idx <= D.window[1])
    if abs(float(raw["pnl"][win].sum()) - float(ev.x.sum())) > 1e-9:
        raise OpenError("per-event P&Ls do not sum to evaluate()'s P&L")
    Hk = D.k * H
    Hc = Hk.copy()
    bind = 0
    on = Hk.abs().sum(axis=1) > 0
    for t in Hk.index[on]:
        w, f = _cap_gross(Hk.loc[t], D.cap)
        Hc.loc[t] = w
        bind += int(f < 1.0)
    trad = evaluate(Hc, R.fillna(0.0))
    pnl, turn = trad["pnl"][win], trad["turn_series"][win]
    st = _stats(pnl, turn)
    grid = {f"{c}bp": {"sr": n_, "ann": st["ann"] - st["turn"] * c / 1e4} for c, n_ in zip(GRID_BP, st["nets"])}
    gross_k = Hk.abs().sum(axis=1)
    cef_cols = [c for c in Hk.columns if c in D.R.columns]
    out = {"H": H, "Hc": Hc, "pnl": pnl, "turn": turn, "cap_binding_rows": bind, "rows_on": int(on.sum()),
           "max_sized_gross": float(gross_k.max()), "max_sized_gross_cef_only": float(Hk[cef_cols].abs().sum(axis=1).max()),
           "gross_sr": st["sr"], "ann": st["ann"], "vol": st["vol"], "turn_yr": st["turn"], "grid": grid,
           "grid_sign_flips": bool(np.sign(st["ann"]) != np.sign(grid["30bp"]["ann"]) or
                                   any(np.sign(v["ann"]) != np.sign(st["ann"]) for v in grid.values()))}
    out["borrow"] = {"B0": {"ann": 0.0}}
    if D.fee_pct is not None:
        bc = borrow_charge(Hc, D.fee_pct.reindex(index=idx, columns=Hc.columns))   # no fee column for MUB/IEF: NaN, reported uncovered if short
        c = bc["cost"][win]
        out["borrow"]["B-meas"] = {"ann": float(c.mean() * 252), "covered_share": float(bc["covered_share"]),
                                   "net_ann": float((pnl - c).mean() * 252), "lower_bound": True}
    return out


# --------------------------------------------------------------------------- the run

def open_core(D: OpenData, d4_from: pd.Timestamp | None = None) -> dict:
    """Every stage of §9.1 on `D`, and every report-only row; the verdict is the first failing rule.

    `d4_from` exists for FIT-descriptive runs only: it starts stage 5's regression where every
    factor exists (MUB from 2007-09). The opening never passes it, so a gap there is a HALT."""
    ev, nx = build_events(D)
    if ev.empty:
        raise OpenError("no eligible event: HALT")
    rep: dict = {"label": D.label, "window": [str(D.window[0].date()), str(D.window[1].date())], "k": D.k,
                 "cap": D.cap, "N": D.n_bar, "exclusions": nx, "limitation": LIMITATION_R10, "notes": list(D.notes)}
    s1 = month_t(ev, "x")
    s1.update({"t_date": date_t(ev, "x"), "boot": month_boot(ev, "x"),
               "pass": bool(s1["mean_bp"] > 0 and s1["t_month"] >= T_BAR)})
    rep["stage1_event_mean"] = s1
    plc, pooled = {}, []
    for sh in PLACEBO_SHIFTS + PLACEBO_REPORT:
        pe, pn = build_events(D, shift=sh, real=ev[["ticker", "ex_date"]])
        plc[f"{sh:+d}"] = {**month_t(pe, "x"), "exclusions": pn}
        if sh in PLACEBO_SHIFTS and len(pe):
            pooled.append(pe)
    if not pooled:
        raise OpenError("no placebo event survives: stage 2 cannot be measured (HALT)")
    pool = pd.concat(pooled)
    pm = float(1e4 * pool.x.mean())
    rep["stage2_placebo"] = {"pooled_mean_bp": pm, "pooled_events": int(len(pool)), "by_shift": plc,
                             "pass": not control_kills(pm, s1["mean_bp"])}
    nvs = ev.dropna(subset=["x_nav"])
    if nvs.empty:
        raise OpenError("no event has a NAV leg: stage 3 cannot be measured (HALT)")
    nv = month_t(nvs, "x_nav")
    price_same = month_t(nvs, "x_unhedged")      # amendment 1: both legs unhedged (the hedge is a price overlay)
    rep["stage3_nav_leg"] = {**nv, "price_mean_same_events_bp": price_same["mean_bp"],
                             "excluded_by_ruling_X5": int(ev.nav_ruled_out.sum()),
                             "no_nav_return": int((ev.x_nav.isna() & ~ev.nav_ruled_out).sum()),
                             "beside_full_set_price_mean_bp": month_t(ev, "x_unhedged")["mean_bp"],
                             "beside_full_set_would_kill": control_kills(nv["mean_bp"], month_t(ev, "x_unhedged")["mean_bp"]),
                             "pass": not control_kills(nv["mean_bp"], price_same["mean_bp"])}       # O3
    e13 = ev[ev.ticker.isin(D.core13)]
    s4 = month_t(e13, "x")
    rep["stage4_13"] = {**s4, "pass": bool(s4["events"] > 0 and s4["mean_bp"] > 0)}
    S = sleeve(D, ev)
    rep["sleeve"] = {k_: S[k_] for k_ in ("cap_binding_rows", "rows_on", "gross_sr", "ann", "vol", "turn_yr", "grid",
                                          "grid_sign_flips", "borrow", "max_sized_gross", "max_sized_gross_cef_only")}
    rep["sleeve"]["cap_binding_share"] = S["cap_binding_rows"] / S["rows_on"] if S["rows_on"] else float("nan")
    p5 = S["pnl"] if d4_from is None else S["pnl"][S["pnl"].index >= d4_from]
    sig = float(p5.std(ddof=1) * math.sqrt(252))
    rep["stage5_d4"] = dimson_d4(p5, D.factors, D.vol_target / sig)          # raises on a gap: HALT
    rep["stage5_d4"]["window"] = [str(p5.index[0].date()), str(p5.index[-1].date())]
    rep["stage6_dsr"] = dsr(S["pnl"], D.n_bar)
    order = [("stage1_event_mean", "KILL D1"), ("stage2_placebo", "KILL (placebo: not the ex-date)"),
             ("stage3_nav_leg", "KILL (NAV leg: a NAV or mark effect)"), ("stage4_13", "KILL D6"),
             ("stage5_d4", "KILL D4"), ("stage6_dsr", "NEITHER")]
    rep["verdict"] = next((v for k_, v in order if not rep[k_]["pass"]), "PASS")
    rep["report_only"] = report_only(D, ev)
    rep["events"], rep["events_13"] = int(len(ev)), int(len(e13))
    return {"report": rep, "events": ev, "sleeve": S}


def report_only(D: OpenData, ev: pd.DataFrame) -> dict:
    """§9.1's report-only rows. None decides anything."""
    ro: dict = {}
    ex_alt, n_alt = build_events(D, unknown="exclude" if D.unknown_mode == "keep" else "keep")
    ro["R10_alternative_basket"] = {"unknown": "exclude" if D.unknown_mode == "keep" else "keep",
                                    **month_t(ex_alt, "x"), "exclusions": n_alt}
    ro["hedge_HD"] = month_t(ev, "x_hd")
    ro["hedge_HYG"] = month_t(ev, "x_hyg")
    ro["eras"] = {lab: month_t(ev[(ev.ex_date >= a) & (ev.ex_date <= b)], "x") for lab, a, b in D.eras}
    if D.regime_split is not None:
        ro["T+2"] = month_t(ev[ev.ex_date < D.regime_split], "x")
        ro["T+1"] = month_t(ev[ev.ex_date >= D.regime_split], "x")
    mu = set(D.munis) | {"MHD", "MQY"}
    ro["taxable"] = month_t(ev[~ev.ticker.isin(mu)], "x")
    ro["muni"] = month_t(ev[ev.ticker.isin(mu)], "x")
    sp = D.exdates[D.exdates.special.fillna(False).astype(bool)]
    spk = set(zip(sp.ticker, sp.ex_date))
    ro["specials"] = month_t(ev[[k_ in spk for k_ in zip(ev.ticker, ev.ex_date)]], "x")
    amt = D.exdates.groupby(["ticker", "ex_date"]).amount_strata.sum()
    yld = pd.Series([amt.get((t, e), np.nan) / D.close_prev.at[D.sessions[p - 1], t]
                     for t, e, p in zip(ev.ticker, ev.ex_date, ev.p)], index=ev.index)
    if yld.notna().sum() >= 8:
        q = pd.qcut(yld.rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"])
        ro["size_quartiles"] = {str(k_): month_t(ev[q == k_], "x") for k_ in ["Q1", "Q2", "Q3", "Q4"]}
    dmin = D.exdates.groupby(["ticker", "ex_date"]).declared.min()
    le2 = [pd.notna(dmin.get((t, e))) and dmin.get((t, e)) <= D.sessions[p - 2] for t, e, p in zip(ev.ticker, ev.ex_date, ev.p)]
    ro["declared_by_e_minus_2"] = month_t(ev[le2], "x")
    if D.shortable_today:
        ro["alpaca_shortable_today"] = {**month_t(ev[[D.shortable_today.get(t) is True for t in ev.ticker]], "x"),
                                        "selects_on_future_information": True}
    if D.rich_cheap is not None:
        z = pd.Series([D.rich_cheap.at[d, t] if (t in D.rich_cheap.columns and d in D.rich_cheap.index) else np.nan
                       for t, d in zip(ev.ticker, ev.decision)], index=ev.index)
        ro["rich_target_lt0"] = month_t(ev[z < 0], "x")
        ro["cheap_target_gt0"] = month_t(ev[z > 0], "x")
        ro["no_target"] = int(z.isna().sum())
    sd = D.R.rolling(63, min_periods=40).std().shift(2)          # 63 sessions ending e-2 at row e
    w = pd.Series([1.0 / sd.at[D.sessions[p], t] if np.isfinite(sd.at[D.sessions[p], t]) else np.nan
                   for t, p in zip(ev.ticker, ev.p)], index=ev.index)
    ro["inverse_vol_unit"] = {**month_t(ev.assign(xw=ev.x * w / w.mean()), "xw"), "events_without_sd": int(w.isna().sum())}
    cap_rows = {}
    for C in CAPITALS:
        notional = D.k * C
        part = [notional / D.adv63.at[D.sessions[p - 2], t] if D.adv63.at[D.sessions[p - 2], t] > 0 else np.nan
                for t, p in zip(ev.ticker, ev.p)]
        px = [D.close_prev.at[D.sessions[p], t] for t, p in zip(ev.ticker, ev.p)]
        rnd = [abs(math.floor(notional / v) * v - notional) / notional if v and np.isfinite(v) else np.nan for v in px]
        cap_rows[f"{C:,.0f}"] = {"median_participation_short_leg": float(np.nanmedian(part)),
                                 "p95_participation": float(np.nanpercentile(part, 95)),
                                 "median_rounding_short_leg": float(np.nanmedian(rnd))}
    ro["capacity"] = cap_rows
    ro["calendar_surprise_cells"] = int(ev.surprise_cells.sum())
    ro["price_only_minus_total_bp"] = float(1e4 * (ev.x_px - ev.x_unhedged).mean())
    if D.hedge_betas is not None:
        g = ev.h_MUB.abs() + ev.h_IEF.abs()
        ro["amendment1_hedge"] = {"mean_h_MUB": float(ev.h_MUB.mean()), "mean_h_IEF": float(ev.h_IEF.mean()),
                                  "share_long_MUB": float((ev.h_MUB > 0).mean()), "share_long_IEF": float((ev.h_IEF > 0).mean()),
                                  "gross_per_event_unit_mean": float(g.mean()), "gross_per_event_unit_max": float(g.max()),
                                  "unhedged_stage1": month_t(ev, "x_unhedged")}
    return ro


# --------------------------------------------------------------------------- loaders

def _returns(close: pd.DataFrame, nav: pd.DataFrame, dist: pd.DataFrame, splits: pd.DataFrame, sessions,
             split_mask: int = 5) -> tuple:
    """r6's total return on price and NAV, and the price-only return, with r6's masks: ±5 sessions
    of a split record (R1: the splits panel) and |r| > 30%. Row t uses closes t-1 and t. An ex-date
    or split that is not a session raises (H15)."""
    close, nav = close.reindex(index=sessions), nav.reindex(index=sessions)
    d = dist[dist.amount > 0]
    off = sorted(set(d.ex_date) - set(sessions))
    if off:
        raise OpenError(f"distribution ex-dates that are not sessions: {[str(x.date()) for x in off[:5]]}")
    div = (d.pivot_table(index="ex_date", columns="ticker", values="amount", aggfunc="sum")
           .reindex(index=sessions, columns=close.columns).fillna(0.0))    # no row = no distribution that day
    R = (close + div) / close.shift(1) - 1.0
    Rpx = close / close.shift(1) - 1.0
    RN = (nav + div) / nav.shift(1) - 1.0
    bad = pd.DataFrame(False, index=sessions, columns=close.columns)
    for r in splits.itertuples():
        if r.ticker in bad.columns:
            if r.ex_date not in set(sessions):
                raise OpenError(f"split {r.ticker} {r.ex_date.date()} is not a session")
            i = sessions.get_loc(r.ex_date)
            bad.iloc[max(0, i - split_mask):i + split_mask + 1, bad.columns.get_loc(r.ticker)] = True
    m = lambda X: X.mask(bad | (X.abs() > 0.30))            # noqa: E731
    return m(R), m(Rpx), m(RN), bad


def _factors(ff: pd.DataFrame, etf: pd.DataFrame, mub: pd.DataFrame) -> pd.DataFrame:
    """Mkt-RF SMB HML RMW CMA UMD (French, decimals); TERM = IEF - RF; HY = HYG - IEF; MUNI = MUB - IEF.
    MUB's total return is (close + dividend) / previous close - 1 on its own rows."""
    E = etf.pivot(index="date", columns="ticker", values="ret_total")
    mub = mub.sort_values("date").set_index("date")
    mub_r = (mub.close + mub.dividend.fillna(0.0)) / mub.close.shift(1) - 1.0   # a no-dividend day is a zero dividend
    f = ff.set_index("date")
    F = f[["mktrf", "smb", "hml", "rmw", "cma", "umd"]].copy()
    F["TERM"] = E["IEF"] - f["rf"]
    F["HY"] = E["HYG"] - E["IEF"]
    F["MUNI"] = mub_r - E["IEF"]
    return F


def load_rehearsal(k: float, cap: float, vol_target: float, n_bar: int, lo="2021-01-01", hedge: bool = True,
                   hi=None) -> OpenData:
    """FIT data only (2021-01-01 .. 2022-12-30), as C4 rehearsed. Every frame is read through a
    parquet filter at FIT_END and asserted. The fit has no declaration dates, so the realised
    calendar is used: every ex-date counts as declared at the calendar's start, so rule 1 cannot
    exclude here (noted). The X4 fills and X5 exclusions are rulings on test cells and do not apply."""
    from scripts.events import exdrift_trial as x
    FE = x.FIT_END
    px = x.read_fit(x.PRICES, ["date", "ticker", "close", "volume"])
    sess = pd.DatetimeIndex(sorted(px["date"].unique()))
    nv = x.read_fit(x.NAVS, ["date", "ticker", "nav"])
    dist = x.read_fit(x.DIST_REFRESH, ["ticker", "ex_date", "amount", "stock_split"], date_col="ex_date")
    sp = pd.read_parquet(x.SPLITS_REFRESH, filters=[("ex_date", "<=", FE), ("ticker", "in", list(x.NAMES))])
    sp["ex_date"] = pd.to_datetime(sp["ex_date"])
    close = px.pivot(index="date", columns="ticker", values="close").reindex(columns=list(x.NAMES))
    vol = px.pivot(index="date", columns="ticker", values="volume").reindex(columns=list(x.NAMES))
    nav = nv.pivot(index="date", columns="ticker", values="nav").reindex(columns=list(x.NAMES))
    R, Rpx, RN, bad = _returns(close, nav, dist, sp, sess)
    ex = dist[dist.amount > 0].groupby(["ticker", "ex_date"]).amount.sum().reset_index()
    ex["amount_strata"] = ex["amount"]
    ex["declared"] = sess[0]                         # the realised calendar (docstring)
    ex["special"] = False
    lo = pd.Timestamp(lo)
    hi = FE if hi is None else min(pd.Timestamp(hi), FE)
    cand = ex[(ex.ex_date >= lo) & (ex.ex_date <= hi)][["ticker", "ex_date"]]
    adv = (close.reindex(sess) * vol.reindex(sess)).rolling(63, min_periods=40).mean()
    ff = pd.read_parquet(x.FF_DAILY, filters=[("date", "<=", FE)])
    etf = pd.read_parquet(x.ETF_DAILY, columns=["date", "ticker", "ret_total"],
                          filters=[("ticker", "in", ["IEF", "HYG"]), ("date", "<=", FE)])
    mub = pd.read_parquet(x.ETF_YF["MUB"], filters=[("date", "<=", FE)])
    for f_ in (ff, etf, mub, sp):
        c = "date" if "date" in f_ else "ex_date"
        f_[c] = pd.to_datetime(f_[c])
        assert not len(f_) or f_[c].max() <= FE
    F = _factors(ff, etf, mub).reindex(sess)
    fee = pd.read_parquet(x.D / "cef" / "cef_borrow_history.parquet",
                          filters=[("ticker", "in", list(x.NAMES)), ("date", "<=", FE)])
    fee["date"] = pd.to_datetime(fee["date"])
    fee = fee.pivot(index="date", columns="ticker", values="fee_rate_pct").reindex(index=sess, columns=list(x.NAMES))
    for f_ in (R, RN, close, F, fee):
        assert f_.index.max() <= FE
    E = etf.pivot(index="date", columns="ticker", values="ret_total")
    mubs = mub.sort_values("date").set_index("date")
    HR = pd.DataFrame({"MUB": (mubs.close + mubs.dividend.fillna(0.0)) / mubs.close.shift(1) - 1.0,
                       "IEF": E["IEF"]}).reindex(sess)
    hb = json.loads(x.HEDGE_JSON.read_text())["betas"] if (hedge and x.HEDGE_JSON.exists()) else None
    if hedge and hb is None:
        raise OpenError(f"{x.HEDGE_JSON.name} does not exist: run `exdrift_trial.py amend1-betas` (fit only)")
    return OpenData(label=f"FIT data {lo.date()}..{hi.date()} (not the test set)"
                    + (", amendment 1 (MUB/IEF hedge)" if hb else ""), sessions=sess, R=R,
                    Rpx=Rpx, RN=RN, masked=bad, exdates=ex, candidates=cand, nav_excluded=set(),
                    close_prev=close.reindex(sess), adv63=adv, factors=F, fee_pct=fee, hyg=E["HYG"].reindex(sess),
                    k=k, cap=cap, vol_target=vol_target, n_bar=n_bar, window=(sess[sess >= lo][0], sess[sess <= hi][-1]),
                    eras=[("2021", pd.Timestamp("2021-01-01"), pd.Timestamp("2021-12-31")),
                          ("2022", pd.Timestamp("2022-01-01"), FE)],
                    core13=tuple(x.CORE), munis=tuple(x.MUNIS),
                    hedge_betas=hb, hedge_R=HR,
                    notes=["rule 1 cannot exclude in the fit (no declaration dates): the realised calendar is used",
                           "X4 fills and X5 exclusions are test-cell rulings and do not apply to the fit",
                           "the rich/cheap split is not computed in the rehearsal"]
                    + (["amendment 1's betas were estimated on 2007-09-11..2022-12-30, which contains this rehearsal "
                        "window: the rehearsal is IN-SAMPLE for the hedge ratios"] if hb else []))


def load_test(token, k: float, cap: float, vol_target: float, n_bar: int, window: tuple) -> OpenData:  # pragma: no cover
    """THE TEST SET (prereg §5.1). Reads 2023+ returns, so it refuses without the token that only
    `exdrift_trial.open_gate` hands out after every check has passed.

    Rulings applied:
    - **X4**: each of the 24 cells is filled from Alpaca's raw SIP close, after C4's adjacent-bar
      check. Alpaca's raw close on e-1 and e+1 must equal yfinance's within X4_BASIS_TOL_USD, or
      the run raises.
    - **X5**: the stale-on-e events and the e+3 repeats are out of the NAV leg.
    - **X1**: Alpaca's amount is used for BIT's strata before 2025-08-19.
    - **R10**: KEEP.
    - **Declarations** come from the committed release table plus the CRSP recovery (the final table)."""
    if token is not _GATE_TOKEN:
        raise OpenError("load_test needs open_gate's token: the test set is opened only through `open`")
    from scripts.cef import band_frontier as bf
    from scripts.events import exdrift_trial as x
    sessions = x.sessions_calendar()
    lo = sessions[max(0, sessions.searchsorted(x.TEST_START) - 80)]           # rolling windows need 63 rows
    q = [("date", ">=", lo), ("ticker", "in", list(x.NAMES))]
    px = pd.read_parquet(x.PRICES, columns=["date", "ticker", "close", "volume"], filters=q)
    nv = pd.read_parquet(x.NAVS, columns=["date", "ticker", "nav"], filters=q)
    for f_ in (px, nv):
        f_["date"] = pd.to_datetime(f_["date"])
        x._only_names(f_, "open")
    close = px.pivot(index="date", columns="ticker", values="close").reindex(index=sessions, columns=list(x.NAMES))
    vol = px.pivot(index="date", columns="ticker", values="volume").reindex(index=sessions, columns=list(x.NAMES))
    bars = pd.read_parquet(x.ALPACA_BARS)
    adj = pd.read_parquet(x.ALPACA_ADJ_BARS)
    for f_ in (bars, adj):
        f_["date"] = pd.to_datetime(f_["date"])
    fills = []
    for r in bars.itertuples():
        if not pd.isna(close.at[r.date, r.ticker]):
            continue
        i = sessions.get_loc(r.date)
        for d in (sessions[i - 1], sessions[i + 1]):
            a = adj[(adj.ticker == r.ticker) & (adj.date == d)]
            if a.empty or not np.isfinite(close.at[d, r.ticker]) or abs(float(a.close.iloc[0]) - close.at[d, r.ticker]) > X4_BASIS_TOL_USD:
                raise OpenError(f"X4 fill {r.ticker} {r.date.date()}: Alpaca's adjacent bar on {d.date()} does not equal "
                                f"yfinance's within ${X4_BASIS_TOL_USD} (the ruled basis check)")
        close.at[r.date, r.ticker] = r.close
        fills.append((r.ticker, str(r.date.date())))
    nav = nv.pivot(index="date", columns="ticker", values="nav").reindex(index=sessions, columns=list(x.NAMES))
    dist = x.read_dist(x.DIST_REFRESH)
    sp = pd.read_parquet(x.SPLITS_REFRESH)
    sp["ex_date"] = pd.to_datetime(sp["ex_date"])
    sp = sp[sp.ticker.isin(x.NAMES)]
    R, Rpx, RN, bad = _returns(close, nav, dist, sp, sessions)
    decl = pd.read_csv(x.DECL_FINAL, parse_dates=["ex_date", "declared"])
    ex = dist[dist.amount > 0].groupby(["ticker", "ex_date"]).amount.sum().reset_index()
    ex = ex.merge(decl[["ticker", "ex_date", "declared"]], on=["ticker", "ex_date"], how="left")
    alp = pd.read_parquet(x.ALPACA_DIVS)
    alp["ex_date"] = pd.to_datetime(alp["ex_date"])
    a_amt = alp.groupby(["ticker", "ex_date"]).amount.sum()
    ex["amount_strata"] = [a_amt.get((t, e), a) if (t == "BIT" and e < pd.Timestamp("2025-08-19")) else a
                           for t, e, a in zip(ex.ticker, ex.ex_date, ex.amount)]
    spc = set(zip(alp[alp.special == True].ticker, alp[alp.special == True].ex_date))   # noqa: E712
    ex["special"] = [k_ in spc for k_ in zip(ex.ticker, ex.ex_date)]
    end_ex = pd.Timestamp(json.loads(x.STAGE0_JSON.read_text())["dg_x1_refresh"]["test_end_ex"])
    cand = ex[(ex.ex_date >= x.TEST_START) & (ex.ex_date <= end_ex)][["ticker", "ex_date"]]
    F_ = pd.read_csv(x.FLAGS, dtype=str, keep_default_na=False)
    nav_ex = set()
    for r in F_.itertuples():
        if r.check == "X5_nav_repeat_on_e" or (r.check == "X5_nav_repeat" and "(e+3)" in r.events):
            for e_ in r.events.split("; "):
                nav_ex.add((r.ticker, pd.Timestamp(e_.split(" ")[0])))
    adv = (close * vol).rolling(63, min_periods=40).mean()
    ff = pd.read_parquet(x.FF_DAILY)
    etf = pd.read_parquet(x.ETF_DAILY, columns=["date", "ticker", "ret_total"], filters=[("ticker", "in", ["IEF", "HYG"])])
    mub = pd.read_parquet(x.ETF_YF["MUB"])
    for f_ in (ff, etf, mub):
        f_["date"] = pd.to_datetime(f_["date"])
    F = _factors(ff, etf, mub).reindex(sessions)
    fee = pd.read_parquet(x.D / "cef" / "cef_borrow_history.parquet", filters=[("ticker", "in", list(x.NAMES))])
    fee["date"] = pd.to_datetime(fee["date"])
    fee = fee.pivot(index="date", columns="ticker", values="fee_rate_pct").reindex(index=sessions, columns=list(x.NAMES))
    probe = sorted((REPO / "results" / "ops" / "alpaca_probe").glob("*_cef.json"))
    short = {t: a.get("shortable") for t, a in json.loads(probe[-1].read_text())["assets"].items()} if probe else {}
    T, _ = bf.build_targets()                         # the deployed book's targets: the rich/cheap split (13 only)
    E = etf.pivot(index="date", columns="ticker", values="ret_total")
    mubs = mub.sort_values("date").set_index("date")
    HR = pd.DataFrame({"MUB": (mubs.close + mubs.dividend.fillna(0.0)) / mubs.close.shift(1) - 1.0,
                       "IEF": E["IEF"]}).reindex(sessions)
    # Amendment 1 (the MUB/IEF hedge) was WITHDRAWN by the team lead on 2026-10-28: the opening runs the
    # ORIGINAL pre-registered design, with no hedge leg.
    return OpenData(label="THE TEST SET (opened once)", sessions=sessions, R=R, Rpx=Rpx, RN=RN, masked=bad, exdates=ex,
                    candidates=cand, nav_excluded=nav_ex, close_prev=close, adv63=adv, factors=F, fee_pct=fee,
                    hyg=E["HYG"].reindex(sessions), k=k, cap=cap, vol_target=vol_target, n_bar=n_bar, window=window,
                    eras=[("2023-24", pd.Timestamp("2023-01-01"), pd.Timestamp("2024-12-31")),
                          ("2025-26", pd.Timestamp("2025-01-01"), pd.Timestamp("2026-12-31"))],
                    core13=tuple(x.CORE), munis=tuple(x.MUNIS), rich_cheap=T, shortable_today=short,
                    hedge_betas=None, hedge_R=None,
                    regime_split=x.T1_START, notes=[f"X4 cells filled from Alpaca SIP: {fills}", LIMITATION_R10,
                                                    "the original design: amendment 1 withdrawn (team lead, 2026-10-28)"])


def write_report(out: dict, path_json: Path, path_txt: Path) -> None:
    rep = out["report"]
    from scripts.events.exdrift_trial import _jsonable
    path_json.write_text(json.dumps(_jsonable(rep), indent=1, sort_keys=True, default=str))
    lines = [f"{rep['label']}: verdict {rep['verdict']}",
             f"window {rep['window']}; k {rep['k']:.4f}; cap {rep['cap']}; N {rep['N']}; events {rep['events']} "
             f"(13: {rep['events_13']})", rep["limitation"]]
    for k_ in ("stage1_event_mean", "stage2_placebo", "stage3_nav_leg", "stage4_13", "stage5_d4", "stage6_dsr", "sleeve"):
        lines.append(f"{k_}: {json.dumps(_jsonable(rep[k_]), default=str)}")
    lines.append(f"report-only: {json.dumps(_jsonable(rep['report_only']), default=str)}")
    lines.append(f"exclusions: {rep['exclusions']}; notes: {rep['notes']}")
    path_txt.write_text("\n".join(lines) + "\n")
