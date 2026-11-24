"""CEF trial 54: C4's discount level against family peers (results/cef/PREREG_C4_LEVEL_2026-11-02.md).

Approved 2026-11-03 (CEF 53 -> 54; §0.A). This script runs the pre-registration's §6.2 in order. Each stage
is a subcommand and is read once:

    python3 -B results/cef/prereg_c4_level/trial54.py dgl2      # DG-L2: CRSP primary vs the yfinance leg
    python3 -B results/cef/prereg_c4_level/trial54.py dgl3      # DG-L3: triage evidence and the rulings check
    python3 -B results/cef/prereg_c4_level/trial54.py fit       # P1, K1-K3, P3 (refuses until DG-L3 is ruled)

NO NEW BACKTESTER. The books are built from C4's own trial machinery (`scripts/cef/c4_families.py`:
`universes`, `load_panels`, `crsp_returns`, `qqqx_rule`, `crsp_pivot`, `build_book`, `declared_mask`,
`check_held`, `yf_total_returns`) and scored by `band_frontier.band_gross_capped` + `band_frontier.evaluate`
(shift(2), H1). The one extension is `level_targets` below. It builds the level weights and the blend with
`build_targets`' own eligibility rule and vol-scalar estimator, line for line, on the same panel. It is
visible here, not hidden in a copy of `evaluate`.

C4'S SPEC IS THE ONLY AUTHORITY ON ITS PARAMETERS. `sizing_multiplier` and `max_gross_stress` are read from
`ops/specs/c4_families.frozen.json` (spec_id asserted to be c4_families.v4.20261102), as
`scripts/cef/c4_paper_benchmark.py` reads it. `build_targets` takes z_window, vol_target, the ADV floor and
min_names from the core spec module, so every one of those is asserted EQUAL to C4's spec value, and a
mismatch raises. `band_width` comes from C4's spec. Nothing is written as a literal.

HOLDOUT. Every frame is cut at 2022-12-30 (`c4.fit_slice`, asserted). The holdout stage is not in this file
yet: it is added, and run once, only after every fit kill and DG-L4 have cleared.

ORDER (§6.2): dgl2 -> dgl3 (signed rulings) -> p1 -> record --variant blend (judged), level, z -> p2 -> k1 -> k2
-> k3 -> p3. Each stage refuses unless every earlier one reads PASS or CLEAR (`need`).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from scripts.cef import band_frontier as bf  # noqa: E402
from scripts.cef import c4_families as c4  # noqa: E402

C4_SPEC = REPO / "ops" / "specs" / "c4_families.frozen.json"
SPEC_ID = "c4_families.v4.20261102"
FIT_END = pd.Timestamp("2022-12-30")
RISK_SHARE_Z = 0.5                 # PREREG §3.1: derived equal risk (0.514 -> 0.50); a trial parameter, not a spec key
SEED = 20261102
DGL2_TOL = 0.2                     # PREREG §4b DG-L2
DGL3_THRESH = 0.10                 # PREREG §4b DG-L3: |price TR - NAV TR| > 10%
STAMP = "2026-11-03"
# PROPOSED for the team lead's ruling (DG-L3), identified by inspection of the NAV paths around the 242 flags and
# by `navscan`; each is a vendor NAV that leaves and returns while the close (CRSP-confirmed) does not follow.
# Recommended treatment: mask the LEVEL leg's discount on these name-days only (the z book is C4's v4 book as
# trading, untouched, so DG-L4's identity is unaffected). Nothing is masked until the rulings file says so.
NAV_MISPRINTS_PROPOSED = {
    ("BME", "2006-07-24"): "NAV 26.35 -> 29.68 -> 27.12, close 24.56 -> 24.98 -> 25.80",
    ("ASG", "2006-12-20"): "NAV 5.71 -> 6.48 -> 5.68, close 5.44 -> 5.39 -> 5.38",
    ("PFO", "2006-12-26"): "NAV 12.40 -> 16.30 (three sessions) -> 12.39, close 12.15 -> 12.30..12.36",
    ("PFO", "2006-12-27"): "the same three-session run",
    ("PFO", "2006-12-28"): "the same three-session run",
    ("JPC", "2008-01-11"): "NAV 12.68 -> 11.35 -> 12.78; the NAV printed equals that day's close (11.35)",
    ("SCD", "2010-10-01"): "NAV 12.93 -> 11.82 -> 12.97, close 11.41 -> 11.42 -> 11.27 (below the 10% flag line)",
    ("BME", "2021-06-28"): "NAV 47.86 -> 27.65 -> 47.79, close 48.78 -> 48.56 -> 48.41 (discount read +75.6%)",
    ("GAM", "2006-04-19"): "NAV 41.46 -> 45.85 -> 41.55 (navscan; outside any crisis window)",
}
CACHE = HERE / "_cache_trial54"


def c4_spec() -> dict:
    d = json.loads(C4_SPEC.read_text())
    if d["spec_id"] != SPEC_ID:
        raise RuntimeError(f"{C4_SPEC}: spec_id {d['spec_id']}, the pre-registration names {SPEC_ID}")
    f = d["frozen"]
    from scripts.cef import spec as core
    pairs = {"z_window": core.Z_WINDOW, "vol_target_annual": core.VOL_TARGET, "min_adv_usd": core.MIN_ADV_USD,
             "min_names": core.MIN_NAMES}
    bad = {k: (f[k], v) for k, v in pairs.items() if float(f[k]) != float(v)}
    if bad:
        raise RuntimeError(f"build_targets reads these from the core spec and they differ from C4's: {bad}")
    return dict(m=float(f["sizing_multiplier"]), cap=float(f["max_gross_stress"]), band=float(f["band_width"]),
                vol=float(f["vol_target_annual"]), min_names=int(f["min_names"]), min_adv=float(f["min_adv_usd"]))


def _rv(W: np.ndarray, ret: np.ndarray, i: int, w: np.ndarray, lookback: int) -> float:
    """build_targets' estimator: today's weights on the last `lookback` rows of price returns through row i."""
    lo = max(0, i - lookback + 1)
    h = np.nansum(ret[lo:i + 1] * w, axis=1)
    return float(np.std(h, ddof=1) * np.sqrt(252)) if len(h) > 1 else np.nan


def level_targets(UF: list, fam: pd.Series, S: dict, level_mask: set | None = None, perm: dict | None = None,
                  blend: bool = True, end: pd.Timestamp | None = None) -> dict:
    """Unit targets T_z (C4's own build_book), T_L (the level with its own scalar) and T_B (the blend), fit cut.

    Eligibility, the hold on thin days and the vol scalar repeat `bf.build_targets` exactly:
    a name needs a z-score on t and ADV >= the floor through t-1; fewer than min_names holds the previous row;
    scalar = clip(vol / rv, 0.2, 2.5), with rv from today's weights on the last VOL_LOOKBACK price returns
    through t (H7: everything here is date-t information; the book is scored under shift(2))."""
    mask = c4.declared_mask(UF, "M1M2")
    p = bf.build_panel(universe=UF, source=c4.FAM_SRC, mask=mask)
    z, adv, disc, ret = p["z"], p["adv"], p["disc"], p["ret"]
    # end None = the fit (fit_slice, asserted). Only `holdout` passes an end, and only after every fit stage cleared.
    Tz = c4.fit_slice(c4.build_book(UF)) if end is None else c4.build_book(UF).loc[:end]
    idx = Tz.index
    # THE VOL ESTIMATOR READS THE FULL HISTORY THROUGH t (fixed 2026-11-03). §1.2 and `build_targets` (and the
    # sleeve's `_book_vol`) take the last 63 sessions of price returns from the panel's whole history. The first
    # build reindexed the returns to the fit index (from 2005-01-03), which truncated the window for the first
    # 62 sessions and broke DG-L4 on 6 sessions, 2005-02-23..03-31 (dgl4_firstread_2026-11-03.json). RF and posF
    # keep the full history; row i of the fit index is row posF[i] of RF, and nothing after it is read (H7).
    retF = ret[UF]
    RF = retF.to_numpy()
    posF = retF.index.get_indexer(idx)
    if (posF < 0).any() or not (retF.index[posF] == idx).all():
        raise AssertionError("the fit index is not a subset of the panel's own index")
    z, adv, disc, ret = (x.reindex(idx)[UF] for x in (z, adv, disc, ret))
    # The LEVEL leg's discount only (DG-L3, signed 2026-11-03): the ruled misprint name-days carry no level.
    # z (and so T_z, C4's v4 book) is untouched.
    disc = disc.copy()
    for (t, d) in (level_mask or set()):
        if t in disc.columns and pd.Timestamp(d) in disc.index:
            disc.at[pd.Timestamp(d), t] = np.nan
    if perm is not None:          # K2's placebo: another fund's level, same family, same date (whole-history shuffle)
        src = disc.copy()
        for f, (cols, order) in perm.items():
            disc[cols] = src[[cols[k] for k in order]].to_numpy()
    TL = np.zeros((len(idx), len(UF)))
    TB = np.zeros_like(TL)
    famv = fam.reindex(UF).to_numpy()
    for i in range(len(idx)):
        zr = z.iloc[i]
        ok = zr.notna().to_numpy() & (adv.iloc[i].fillna(-1).to_numpy() >= S["min_adv"])
        if ok.sum() < S["min_names"]:
            if i:
                TL[i], TB[i] = TL[i - 1], TB[i - 1]
            continue
        # w_z: build_targets' own unit-gross weights (recomputed only to take their vol; T_z itself is build_book's)
        zz = np.where(ok, zr.to_numpy(), np.nan)
        wz = -(zz - np.nanmean(zz))
        wz = np.where(ok, wz, 0.0)
        wz = wz / np.abs(wz).sum()
        # w_L: -(disc - family mean), on the same eligible names; a family with < 2 eligible names gets zero
        dv = np.where(ok, disc.iloc[i].to_numpy(), np.nan)
        wl = np.zeros(len(UF))
        for f in pd.unique(famv[ok]):
            sel = ok & (famv == f) & np.isfinite(dv)
            if sel.sum() >= 2:
                wl[sel] = -(dv[sel] - dv[sel].mean())
        if np.abs(wl).sum() == 0:
            if i:
                TL[i], TB[i] = TL[i - 1], TB[i - 1]
            continue
        wl = wl / np.abs(wl).sum()
        j = posF[i]                                       # row t of the full history
        s_z, s_l = _rv(None, RF, j, wz, bf.VOL_LOOKBACK), _rv(None, RF, j, wl, bf.VOL_LOOKBACK)
        sc = lambda rv: float(np.clip(S["vol"] / rv, 0.2, 2.5)) if rv and rv > 0 else 1.0   # build_targets' rule
        TL[i] = wl * sc(s_l)
        if not blend:
            continue
        if not (s_z > 0 and s_l > 0):
            TB[i] = TB[i - 1] if i else 0.0
            continue
        mix = RISK_SHARE_Z * wz / s_z + (1 - RISK_SHARE_Z) * wl / s_l
        mix = mix / np.abs(mix).sum()
        TB[i] = mix * sc(_rv(None, RF, j, mix, bf.VOL_LOOKBACK))
    TL = pd.DataFrame(TL, index=idx, columns=UF)
    TB = pd.DataFrame(TB, index=idx, columns=UF)
    for f in (Tz, TL, TB):
        if end is None and f.index.max() > FIT_END:
            raise AssertionError("holdout leak in a target")
    return dict(Tz=Tz, TL=TL, TB=TB, disc=disc)


def book(T: pd.DataFrame, S: dict, band: float | None = None) -> pd.DataFrame:
    """The account's held book: m x band_gross_capped(unit target, band, cap / m) -- the sizing_multiplier path."""
    b = S["band"] if band is None else band
    return bf.band_gross_capped(T, b, S["cap"] / S["m"]) * S["m"]


def score(H: pd.DataFrame, R: pd.DataFrame, label: str) -> dict:
    R0 = c4.check_held(H, R.reindex(H.index)[H.columns], label)
    res = bf.evaluate(H, R0)
    held = H.shift(2).abs().sum(axis=1)
    p0 = held.index[held > 0][0]
    P, TU = res["pnl"].loc[p0:FIT_END], res["turn_series"].loc[p0:FIT_END]
    return dict(P=P, TU=TU, p0=p0, **c4.row_stats(P, TU))


def inputs():
    U = c4.universes()
    pool, UF = U["pool"], U["frozen"]
    px, nav = c4.load_panels(pool)
    crsp = c4.crsp_returns(pool)
    qr = c4.qqqx_rule(crsp, px)
    if not qr["use_predecessor"]:
        raise RuntimeError("the QQQX rule's decision differs from C4's Stage 0")
    fam = pd.read_csv(c4.FROZEN).set_index("ticker")["family"]
    return U, pool, UF, px, nav, crsp, qr, fam


def stage_dgl2() -> int:
    lines = []
    say = lambda s="": (print(s), lines.append(s))
    S = c4_spec()
    U, pool, UF, px, nav, crsp, qr, fam = inputs()
    say(f"CEF trial 54, DG-L2 ({dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}): "
        f"C4 spec {SPEC_ID}: m {S['m']}, cap {S['cap']}, band {S['band']}")
    B = level_targets(UF, fam, S)
    idx = B["Tz"].index
    R_crsp = c4.crsp_pivot(crsp, pool, idx, qr, "ret", px=px)
    # the yfinance leg exactly as C4's primary_returns builds it (bar rulings + split rulings)
    R_yf = c4.yf_total_returns(px, UF, idx, rulings=c4.BAR_RULINGS, split_rulings=c4.SPLIT_RULINGS)
    HL = book(B["TL"], S)
    out = {}
    for lab, R in (("CRSP primary", R_crsp), ("yfinance leg", R_yf)):
        r = score(HL, R, f"level book on {lab}")
        out[lab] = {k: r[k] for k in ("sr", "ann_pct", "vol_pct", "turn")}
        say(f"  level-only spec book on {lab:<13}: gross SR {r['sr']:+.3f}  ann {r['ann_pct']:+.2f}%  vol {r['vol_pct']:.2f}%  "
            f"turn {r['turn']:.1f}/yr  (from {r['p0'].date()})")
    d = abs(out["CRSP primary"]["sr"] - out["yfinance leg"]["sr"])
    verdict = "CLEAR" if d <= DGL2_TOL else "HALT (difference > 0.2; explain or stop)"
    say(f"  |difference| {d:.3f} against {DGL2_TOL}: DG-L2 {verdict}")
    (HERE / f"dgl2_output_{STAMP}.txt").write_text("\n".join(lines) + "\n")
    (HERE / f"dgl2_{STAMP}.json").write_text(json.dumps(dict(spec=SPEC_ID, **S, books=out, diff=d, verdict=verdict),
                                                          indent=1, default=float))
    return 0 if d <= DGL2_TOL else 2


def stage_dgl3() -> int:
    """The 242 flags, with their evidence and a RECOMMENDED ruling per flag. A recommendation is not a ruling:
    `fit` refuses until a rulings file signed by the team lead exists (require_stage0_rulings)."""
    from scripts.cef.data_guards import require_stage0_rulings  # noqa: F401  (the block `fit` uses)
    lines = []
    say = lambda s="": (print(s), lines.append(s))
    S = c4_spec()
    U, pool, UF, px, nav, crsp, qr, fam = inputs()
    sys.path.insert(0, str(REPO / "results" / "cef" / "screens_2026-11-02"))
    import alpha_common as ac
    D = ac.load_c4()                          # the leg the 242 were counted on (ALPHA_SLATE §S5)
    gap = (D["r_tr"] - D["r_nav_tr"])
    hit = gap.abs() > DGL3_THRESH
    s = hit.stack()
    s = s[s].index
    idx = D["idx"]
    R = c4.crsp_pivot(crsp, pool, idx, qr, "ret", px=px)
    cc = pd.read_parquet(c4.FAM_DIR / "cef_nav_cefconnect.parquet")
    cc["date"] = pd.to_datetime(cc["date"])
    ccn = cc.pivot_table(index="date", columns="ticker", values="nav")
    rules = {k: json.loads(Path(p).read_text()) for k, p in
             (("split", c4.SPLIT_RULINGS), ("bar", c4.BAR_RULINGS),
              ("seed", c4.OUT_DIR / "c4_seed_rulings_2026-10-29.json"))}
    ruled_cells = set()
    for k, j in rules.items():
        for r in [x for key in ("bars", "cells", "splits") for x in (j.get(key) or [])]:
            if isinstance(r, dict) and "ticker" in r and ("date" in r or "ex_date" in r):
                ruled_cells.add((r["ticker"], str(r.get("date") or r.get("ex_date"))[:10], k))
    crisis = lambda d: (pd.Timestamp("2008-09-01") <= d <= pd.Timestamp("2009-06-30")) or \
                       (pd.Timestamp("2020-02-20") <= d <= pd.Timestamp("2020-04-30"))
    rows = []
    for d, t in s:
        i = idx.get_loc(d)
        dp = idx[i - 1]
        c0 = ccn.at[dp, t] if (dp in ccn.index and t in ccn.columns) else np.nan
        c1 = ccn.at[d, t] if (d in ccn.index and t in ccn.columns) else np.nan
        nxt = D["r_nav_tr"].iat[i + 1, D["U"].index(t)] if i + 1 < len(idx) else np.nan
        cr = R.at[d, t] if t in R.columns else np.nan
        r = dict(ticker=t, date=d.date().isoformat(), family=fam.get(t), yf_price_tr=float(D["r_tr"].at[d, t]),
                 crsp_ret=float(cr), nav_tr=float(D["r_nav_tr"].at[d, t]), nav_tr_next=float(nxt),
                 nav_prev=float(D["nav"].at[dp, t]), nav=float(D["nav"].at[d, t]), cc_nav_prev=float(c0),
                 cc_nav=float(c1), crisis_window=bool(crisis(d)),
                 c4_ruling=";".join(k for (tk, dd, k) in ruled_cells if tk == t and dd == d.date().isoformat()))
        r["price_confirmed_by_crsp"] = bool(np.isfinite(cr) and abs(r["yf_price_tr"] - cr) <= 0.005)
        r["nav_confirmable"] = bool(np.isfinite(c0) and np.isfinite(c1))
        # a NAV SPIKE: the NAV leg itself moves >= 5% and gives back more than half of it the next session
        r["nav_spike_reverts"] = bool(abs(r["nav_tr"]) >= 0.05 and np.sign(r["nav_tr"]) != np.sign(nxt)
                                      and abs(nxt) > 0.5 * abs(r["nav_tr"]))
        prev_s = idx[i - 1].date().isoformat()
        if (t, r["date"]) in NAV_MISPRINTS_PROPOSED:
            rec, why = "MASK (recommended)", ("vendor NAV misprint, " + NAV_MISPRINTS_PROPOSED[(t, r["date"])] +
                                              "; mask the level leg's discount on this name-day; its return books")
        elif (t, prev_s) in NAV_MISPRINTS_PROPOSED:
            rec, why = "KEEP (recommended)", (f"the day after the NAV misprint of {prev_s}; the flag is that misprint's "
                                              "echo and is resolved by masking that day; this NAV is good again")
        elif r["c4_ruling"]:
            rec, why = "APPLY C4 RULING", f"covered by C4's {r['c4_ruling']} ruling"
        elif not r["price_confirmed_by_crsp"]:
            rec, why = "KEEP (recommended)", ("the yfinance price TR disagrees with CRSP's, but the trial books CRSP's "
                                              "return (§4) and the level uses the yfinance close and NAV, which share "
                                              "a basis; the disagreement is the distribution leg, not the close")
        elif not r["nav_spike_reverts"]:
            rec, why = "KEEP (recommended)", ("price leg confirmed by CRSP (an independent source); the NAV is not a "
                                              "one-day spike; C4 keeps an unmasked NAV (its M1|M2 masks are its NAV "
                                              "policy). A real discount move")
        elif r["crisis_window"]:
            rec, why = "KEEP (recommended)", ("price confirmed by CRSP; a NAV spike that reverts inside the 2008-09 or "
                                              "2020 crisis window is a plausible marked move; no second NAV source "
                                              "covers the day")
        else:
            rec, why = "MASK (recommended)", ("a one-day NAV spike (>= 5%, more than half given back next session) "
                                              "outside a crisis window, with the price flat and confirmed by CRSP: a "
                                              "vendor NAV misprint. Mask that name-day's discount as C4's M1 does "
                                              "(build_panel `mask`); its return still books")
        r["recommended"], r["why"] = rec, why
        rows.append(r)
    F = pd.DataFrame(rows).sort_values(["date", "ticker"])
    F.insert(0, "check", "DG-L3")
    # CRSP is licensed and the repository is public: the committed table carries the CHECK, never CRSP's value
    F.drop(columns=["crsp_ret"]).to_csv(HERE / f"dgl3_flags_{STAMP}.csv", index=False)
    prop = F[["check", "ticker", "date"]].assign(ruling=F.recommended + ": " + F.why, ruled_by="", ruled_on="")
    extra = [dict(check="DG-L3-NAV", ticker=t, date=d, ruling="MASK (recommended): vendor NAV misprint, " + why +
                  "; not among the 242 (below the 10% line); mask the level leg's discount", ruled_by="", ruled_on="")
             for (t, d), why in NAV_MISPRINTS_PROPOSED.items() if (t, d) not in set(zip(F.ticker, F.date))]
    prop = pd.concat([prop, pd.DataFrame(extra)], ignore_index=True)
    prop.to_csv(HERE / f"dgl3_rulings_PROPOSAL_{STAMP}.csv", index=False)
    say(f"CEF trial 54, DG-L3 ({STAMP}): {len(F)} name-days with |price TR - NAV TR| > {DGL3_THRESH:.0%} on the fit's "
        f"yfinance leg")
    say(f"  by year: {F.date.str[:4].value_counts().sort_index().to_dict()}")
    say(f"  price leg confirmed by CRSP (|yf - CRSP| <= 50bp): {int(F.price_confirmed_by_crsp.sum())}; "
        f"NAV confirmable by CEFConnect (both days present): {int(F.nav_confirmable.sum())}; "
        f"NAV spike reverts next day: {int(F.nav_spike_reverts.sum())}; in a crisis window: {int(F.crisis_window.sum())}; "
        f"covered by a C4 split/bar/seed ruling: {int((F.c4_ruling != '').sum())}")
    say(f"  RECOMMENDED on the 242: {F.recommended.value_counts().to_dict()}; plus "
        f"{sum((t, d) not in set(zip(F.ticker, F.date)) for (t, d) in NAV_MISPRINTS_PROPOSED)} NAV-misprint name-days "
        f"below the 10% line (DG-L3-NAV rows); {len(NAV_MISPRINTS_PROPOSED)} misprint name-days proposed in all")
    for _, r in F[~F.recommended.str.startswith("KEEP") | ~F.price_confirmed_by_crsp].iterrows():
        say(f"    {r.recommended}: {r.ticker} {r.date}: yf price TR {r.yf_price_tr:+.2%}, CRSP agrees: {r.price_confirmed_by_crsp}, NAV TR "
            f"{r.nav_tr:+.2%} then {r.nav_tr_next:+.2%}; NAV {r.nav_prev:.2f} -> {r.nav:.2f}")
    ruled = HERE / f"dgl3_rulings_{STAMP}.csv"
    say(f"  every flag needs a ruling (§4b). Proposal: dgl3_rulings_PROPOSAL_{STAMP}.csv (keys + recommended ruling; "
        f"ruled_by / ruled_on blank). The team lead signs it into {ruled.name}.")
    say(f"  rulings file {ruled.name}: {'PRESENT' if ruled.exists() else 'ABSENT: the fit refuses until the team lead rules'}")
    (HERE / f"dgl3_output_{STAMP}.txt").write_text("\n".join(lines) + "\n")
    return 0




# ============================================================================ the fit stages (§6.2, read in order)

FLAGS_PROPOSAL = HERE / f"dgl3_rulings_PROPOSAL_{STAMP}.csv"
RULINGS = HERE / f"dgl3_rulings_{STAMP}.csv"
BAR = float(np.sqrt(2 * np.log(54)))
DSR_PASS = c4.DSR_PASS
NC1_T = 2.0
PLACEBO_N, PLACEBO_NEED = 20, 19
H2_TOL = 0.05


def ruled_masks() -> set:
    """The signed DG-L3 rulings, through the house block: no P&L while any flag lacks a ruling."""
    from scripts.cef.data_guards import require_stage0_rulings
    flags = pd.read_csv(FLAGS_PROPOSAL)[["check", "ticker", "date"]]
    J = require_stage0_rulings(flags, RULINGS, context="CEF trial 54 DG-L3")
    m = J[J["ruling"].str.startswith("MASK")]
    return set(zip(m["ticker"], m["date"].astype(str)))


def verdict_of(stage: str) -> str:
    f = HERE / f"{stage}_{STAMP}.json"
    if not f.exists():
        raise RuntimeError(f"{stage} has not been read; §6.2 reads the kills in order")
    return json.loads(f.read_text())["verdict"]


K3_OVERRIDE = HERE / f"k3_override_{STAMP}.json"


def need(*stages):
    """Every earlier stage must read PASS or CLEAR. ONE recorded exception: K3, which FAILED as committed
    (KILL D4) and was overridden POST-DATA by the team lead on 2026-11-03 ("revive it and figure out a way to
    not kill it"; k3_override_2026-11-03.json; docs/SYSTEM.md §5). That is not a pass of K3: k3's own output
    still reads KILL, and this function lets the pre-registered remainder run past it and nothing else."""
    for st in stages:
        v = verdict_of(st)
        if st == "k3" and v.startswith("KILL") and K3_OVERRIDE.exists():
            o = json.loads(K3_OVERRIDE.read_text())
            if o.get("stage") == "k3" and o.get("is_a_pass") is False and o.get("ruled_by", "").startswith("team lead"):
                continue
        if not v.startswith("PASS") and not v.startswith("CLEAR"):
            raise RuntimeError(f"{st} reads {v}; the trial stopped there (stop at the first KILL)")


def write(stage: str, lines: list, out: dict) -> None:
    (HERE / f"{stage}_output_{STAMP}.txt").write_text("\n".join(lines) + "\n")
    (HERE / f"{stage}_{STAMP}.json").write_text(json.dumps(out, indent=1, default=float))


def books(S: dict, masks: set) -> dict:
    """The three books on CRSP primary returns, fit only, and their series (cached, gitignored)."""
    U, pool, UF, px, nav, crsp, qr, fam = inputs()
    B = level_targets(UF, fam, S, level_mask=masks)
    idx = B["Tz"].index
    R = c4.crsp_pivot(crsp, pool, idx, qr, "ret", px=px)
    out = dict(R=R, B=B, UF=UF, fam=fam)
    for k, T in (("z", B["Tz"]), ("level", B["TL"]), ("blend", B["TB"])):
        out[k] = score(book(T, S), R, f"{k} book")
    return out


def _hac_alpha(y: pd.Series, x: pd.Series, lag: int):
    import statsmodels.api as sm
    d = pd.concat([y.rename("y"), x.rename("x")], axis=1).dropna()
    f = sm.OLS(d["y"], sm.add_constant(d[["x"]])).fit(cov_type="HAC", cov_kwds={"maxlags": lag})
    return f, d


def stage_p1() -> int:
    from scripts.cef import w4_artifacts as w4
    need("dgl2")
    masks = ruled_masks()
    S = c4_spec()
    lines = []
    say = lambda s_="": (print(s_), lines.append(s_))
    K = books(S, masks)
    CACHE.mkdir(parents=True, exist_ok=True)
    for k in ("z", "level", "blend"):
        K[k]["P"].rename("pnl").to_frame().to_parquet(CACHE / f"pnl_{k}.parquet")
        K[k]["TU"].rename("turn").to_frame().to_parquet(CACHE / f"turn_{k}.parquet")
    for k in ("Tz", "TL", "TB"):
        K["B"][k].to_parquet(CACHE / f"target_{k}.parquet")
    say(f"CEF trial 54, P1 ({dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}); C4 spec {SPEC_ID}: m {S['m']}, "
        f"cap {S['cap']}, band {S['band']}; DG-L3 masks on the level leg: {len(masks)}; CRSP primary returns; fit only")
    for k, lab in (("z", "z-only spec book"), ("level", "level-only spec book"), ("blend", "blend (1/2 : 1/2)")):
        r = K[k]
        say(f"  {lab:<22} gross SR {r['sr']:+.3f}  ann {r['ann_pct']:+.2f}%  vol {r['vol_pct']:.2f}%  turn {r['turn']:.1f}/yr  "
            f"net @5/15/30 {r['net5']:+.3f} / {r['net15']:+.3f} / {r['net30']:+.3f}  flips {r['flips']}  (from {r['p0'].date()})")
    y, x = K["level"]["P"], K["z"]["P"]
    start = max(K["level"]["p0"], K["z"]["p0"])
    y, x = y.loc[start:], x.loc[start:]
    f0, d = _hac_alpha(y, x, 0)
    L = w4.nw_auto_lag(f0.resid)
    f, d = _hac_alpha(y, x, L)
    t, a, b = float(f.tvalues["const"]), float(f.params["const"]) * 252 * 100, float(f.params["x"])
    side = {lag: float(_hac_alpha(y, x, lag)[0].tvalues["const"]) for lag in (5, 21)}
    ok = t >= BAR
    verdict = "PASS" if ok else "KILL (D1)"
    say(f"  P1: level-only on z-only, {len(d)} sessions {d.index[0].date()}..{d.index[-1].date()}: alpha {a:+.2f}%/yr, beta {b:+.3f}, "
        f"NW t {t:.2f} (Newey-West 1994 automatic lag {L} on the residual); beside it t at L=5 {side[5]:.2f}, L=21 {side[21]:.2f}")
    say(f"  rule NW t >= sqrt(2 ln 54) = {BAR:.3f}: {verdict}")
    write("p1", lines, dict(verdict=verdict, alpha_t=t, alpha_pct=a, beta=b, lag=L, t_L5=side[5], t_L21=side[21],
                            n=len(d), bar=BAR, masks=len(masks), spec=SPEC_ID, m=S["m"], cap=S["cap"], band=S["band"],
                            books={k: {kk: K[k][kk] for kk in ("sr", "ann_pct", "vol_pct", "turn", "net5", "net15", "net30",
                                                               "flips")} | {"first_held": str(K[k]["p0"].date())}
                                   for k in ("z", "level", "blend")}))
    return 0 if ok else 3


def stage_record(variant: str) -> int:
    """Store a series in the registry (CEF-54). The tree must be clean (registry.record refuses otherwise)."""
    from scripts.research import registry
    need("p1")
    # The first read stored blend (judged), level and z; a judged line is never replaced. The corrected book
    # (2ed752f: the full-history vol lookback) is stored under NEW, unjudged names; z's book did not change.
    src = {"blend": "blend", "level": "level", "z": "z", "blend_corrected": "blend", "level_corrected": "level"}[variant]
    P = pd.read_parquet(CACHE / f"pnl_{src}.parquet")["pnl"]
    S = c4_spec()
    line = registry.record(P, counter="CEF", trial="CEF-54", variant=variant, judged=(variant == "blend"),
                           params=dict(spec=SPEC_ID, m=S["m"], cap=S["cap"], band=S["band"], risk_share_z=RISK_SHARE_Z,
                                       returns="CRSP primary (C4's fit source), total return", fit_end=str(FIT_END.date()),
                                       dgl3_masks=len(ruled_masks())),
                           note=f"CEF trial 54 ({variant} book), results/cef/prereg_c4_level/trial54.py p1; fit only")
    print(json.dumps({k: line[k] for k in ("trial", "variant", "judged", "n", "sr_annual", "sha256", "commit", "dirty")}))
    return 0


def stage_p2() -> int:
    from scripts.research import registry
    need("dgl2", "p1")
    lines = []
    say = lambda s_="": (print(s_), lines.append(s_))
    # THE CORRECTED READ (2ed752f). The judged ledger line is the first read's blend, and `registry.bars` gives
    # bars on the judged series only. The corrected blend is stored as CEF-54/blend_corrected (unjudged), so its
    # desk DSR is computed here with the registry's own functions on its stored bytes, exactly as `bars` does
    # (T, per-period SR, pandas skew, kurt + 3, desk_dsr at the declared N). The paper bar's refusal depends on
    # the counter, not the series, so `bars` on the judged first read supplies it, and it is shown beside.
    from scripts.research.inference import desk_dsr, upper_bound_max_z
    hit = [e for e in registry.entries("CEF", trials=["CEF-54"]) if e["variant"] == "blend_corrected"]
    if len(hit) != 1:
        raise RuntimeError("CEF-54/blend_corrected is not stored once in the ledger; run `record --variant blend_corrected`")
    xs = registry.load(hit[0])
    x = xs.to_numpy(dtype=float)
    T = len(x)
    sr = float(x.mean() / x.std(ddof=1))
    skew, kurt = float(pd.Series(x).skew()), float(pd.Series(x).kurt() + 3.0)
    r = registry.bars("CEF", trial="CEF-54", variant="blend", declared_n=54)
    r_first = dict(desk_dsr=r["desk"]["dsr"], sr_annual=r["sr_annual"], T=r["T"])
    r["T"], r["sr_annual"], r["skew"], r["kurt"] = T, sr * np.sqrt(252), skew, kurt
    r["desk"] = dict(n_trials=54, T=T, sr0=np.sqrt(1 / T) * upper_bound_max_z(54),
                     sr0_annual=np.sqrt(1 / T) * upper_bound_max_z(54) * np.sqrt(252),
                     dsr=desk_dsr(sr * np.sqrt(252), T, skew, kurt, 54))
    r["series"] = "CEF-54/blend_corrected (sha256 " + hit[0]["sha256"][:12] + ")"
    r["first_read"] = r_first
    desk = r["desk"]["dsr"]
    paper = r["paper"]["dsr"] if r["paper"] else None
    # WHICH BAR GATES is the team lead's, read from docs/SYSTEM.md §5 (registry.bars' docstring). The row "Which bar
    # gates the CEF counter, ruled 2026-10-28" reads: the desk's sqrt(2 ln N) on the raw counter, unchanged; the
    # paper's switch condition can never be met for CEF. So on CEF the paper bar is refused by construction
    # (code not_qualified) and the desk bar gates. PREREG §6.2's "both bars" was drafted without that row; the
    # standing ruling governs, and the output says so. Any OTHER refusal halts for a ruling.
    rule_row = "Which bar gates the CEF counter, ruled **2026-10-28**"
    if rule_row not in (REPO / "docs" / "SYSTEM.md").read_text():
        raise RuntimeError("docs/SYSTEM.md §5 no longer carries the 2026-10-28 CEF bar ruling; re-read it before P2")
    if paper is not None:
        ok = desk >= DSR_PASS and paper >= DSR_PASS
        verdict = "PASS" if ok else "KILL"
    elif r["paper_refused_code"] == "not_qualified":
        ok = desk >= DSR_PASS
        verdict = ("PASS (the desk bar gates CEF: docs/SYSTEM.md §5, 2026-10-28; the paper bar is refused by "
                   "construction, not_qualified)") if ok else "KILL"
    else:
        ok, verdict = False, f"HALT (paper bar refused, {r['paper_refused_code']}: a ruling)"
    say(f"  first read (trial script bug: truncated vol lookback, 6 sessions 2005-02-23..03-31): judged CEF-54/blend, "
        f"desk DSR {r_first['desk_dsr']:.4f}, SR {r_first['sr_annual']:.3f}/yr")
    say(f"CEF trial 54, P2 on {r['series']} (T {r['T']}, SR {r['sr_annual']:.3f}/yr, skew "
        f"{r['skew']:.2f}, kurt {r['kurt']:.2f})")
    say(f"  desk bar: SR0 {r['desk']['sr0_annual']:.3f}/yr, DSR {desk:.4f}")
    if r["paper"]:
        p = r["paper"]
        say(f"  paper bar: N_eff {p['n_effective']:.2f}, rho_bar {p['rho_bar']:.3f}, floor binds {p['floor_binds']}, SR0 "
            f"{p['sr0_annual']:.3f}/yr, DSR {paper:.4f}")
    else:
        say(f"  paper bar REFUSED: {r['paper_refused']} ({r['paper_refused_code']})")
    say(f"  rule: DSR >= {DSR_PASS} on the bar(s) that gate CEF: {verdict}")
    write("p2", lines, dict(verdict=verdict, bars=r))
    return 0 if ok else 4


def stage_k1() -> int:
    """NC1 on the leg the screen measured it on: the level's slope on the NAV total-return leg (h 21, z in,
    within family, date-clustered), with the ruled masks on the level."""
    need("dgl2", "p1", "p2")
    masks = ruled_masks()
    sys.path.insert(0, str(REPO / "results" / "cef" / "screens_2026-11-02"))
    import alpha_common as ac
    lines = []
    say = lambda s_="": (print(s_), lines.append(s_))
    D = ac.load_c4()
    disc = D["disc"].copy()
    for (t, d) in masks:
        if t in disc.columns and pd.Timestamp(d) in disc.index:
            disc.at[pd.Timestamp(d), t] = np.nan
    elig = D["z"].notna() & disc.notna()
    lvl = ac.cs_demean(disc.where(elig), D["grp"])
    zz = ac.cs_demean(D["z"].where(elig), D["grp"])
    grid = D["idx"][::21]
    res = {}
    for lab, r in (("NAV TR (NC1)", D["r_nav_tr"]), ("price TR", D["r_tr"]), ("discount leg", D["r_tr"] - D["r_nav_tr"])):
        y = ac.cs_demean(ac.fwd(r, 2, 21).where(elig), D["grp"]) * 1e4
        o = ac.pooled_ols(y, {"lvl": lvl, "z": zz}, grid, min_n=ac.MIN_NAMES)
        res[lab] = dict(coef=o["lvl"]["coef"], t=o["lvl"]["t"], n=o["n"], dates=o["dates"])
        say(f"  {lab:<14}: level slope {o['lvl']['coef']:+.2f} bp/pp, t {o['lvl']['t']:+.2f} (n {o['n']}, {o['dates']} dates)")
    t = res["NAV TR (NC1)"]["t"]
    verdict = "PASS" if abs(t) < NC1_T else "KILL (D1)"
    say(f"  rule |t| < {NC1_T} on the NAV leg: {verdict}")
    write("k1", ["CEF trial 54, K1 (NC1): the level slope by leg, h 21, z in, within family (yfinance leg; masks applied)"]
          + lines, dict(verdict=verdict, legs=res, masks=len(masks)))
    return 0 if abs(t) < NC1_T else 5


def stage_k2() -> int:
    need("dgl2", "p1", "p2", "k1")
    masks = ruled_masks()
    S = c4_spec()
    U, pool, UF, px, nav, crsp, qr, fam = inputs()
    lines = []
    say = lambda s_="": (print(s_), lines.append(s_))
    real = json.loads((HERE / f"p1_{STAMP}.json").read_text())["books"]["level"]["sr"]
    idx = pd.read_parquet(CACHE / "target_Tz.parquet").index
    R = c4.crsp_pivot(crsp, pool, idx, qr, "ret", px=px)
    rng = np.random.default_rng(SEED)
    fam_cols = {f: [t for t in UF if fam.get(t) == f] for f in sorted(set(fam.reindex(UF).dropna()))}
    sr = []
    for k in range(PLACEBO_N):
        perm = {f: (cols, rng.permutation(len(cols))) for f, cols in fam_cols.items() if len(cols) > 1}
        B = level_targets(UF, fam, S, level_mask=masks, perm=perm, blend=False)
        sr.append(score(book(B["TL"], S), R, f"placebo {k}")["sr"])
        say(f"  placebo {k + 1:>2}: gross SR {sr[-1]:+.3f}")
    above = int(sum(x < real for x in sr))
    verdict = "PASS" if above >= PLACEBO_NEED else "KILL (D1)"
    say(f"  real level-only book {real:+.3f} ranks above {above} of {PLACEBO_N} (placebo mean {np.mean(sr):+.3f}, max "
        f"{np.max(sr):+.3f}); rule >= {PLACEBO_NEED}: {verdict}")
    write("k2", ["CEF trial 54, K2: within-family shuffle placebo (another fund's level, same family; seed "
                 f"{SEED}; the level-only spec book on CRSP)"] + lines, dict(verdict=verdict, real=real, placebo=sr, above=above))
    return 0 if above >= PLACEBO_NEED else 6


def stage_k3() -> int:
    need("dgl2", "p1", "p2", "k1", "k2")
    S = c4_spec()
    lines = []
    say = lambda s_="": (print(s_), lines.append(s_))
    X = c4.factor_frame()
    res, ok = {}, True
    for k in ("level", "blend"):
        P = pd.read_parquet(CACHE / f"pnl_{k}.parquet")["pnl"]
        sig = float(P.std() * np.sqrt(252))
        scale = S["vol"] / sig
        A = c4.dimson(P, X, c4.FF6 + ["TERM"], scale)
        PB = P.loc[max(c4.HY_START, P.index[0]):FIT_END]
        Bq = c4.dimson(PB, X, c4.FF6 + ["TERM", "HY"], scale)
        okA = A["alpha_t"] >= c4.D4_ALPHA_T and A["max_abs_beta"] <= c4.D4_BETA
        okB = Bq["alpha_t"] >= c4.D4_ALPHA_T and Bq["max_abs_beta"] <= c4.D4_BETA
        res[k] = dict(full=A, hy=Bq, pass_=bool(okA and okB), scale=scale)
        for lab, r_, o in (("full fit, FF6+TERM", A, okA), ("from HYG, +HY", Bq, okB)):
            say(f"  {k:<6} {lab:<20} n {r_['n']} alpha {r_['alpha_pct']:+.2f}%/yr t {r_['alpha_t']:.2f} max|beta| "
                f"{r_['max_abs_beta']:.3f} ({', '.join(f'{c} {v:+.3f}' for c, v in r_['betas'].items())}) -> {'pass' if o else 'FAIL'}")
        if k == "level":
            ok = okA and okB
    verdict = "PASS" if ok else "KILL (D4)"
    say(f"  rule (C4's D4 block, on the level-only book): alpha t >= {c4.D4_ALPHA_T} and every |beta| <= {c4.D4_BETA} in "
        f"both: {verdict}  (the blend is reported beside it)")
    write("k3", ["CEF trial 54, K3 (D4): Dimson FF5+UMD, TERM, HY at t and t-1, HAC(21), betas scaled to the spec's vol "
                 "target"] + lines, dict(verdict=verdict, results=res))
    return 0 if ok else 7


def stage_p3() -> int:
    from scripts.research.resampling import calibrate_block, sharpe_diff
    need("dgl2", "p1", "p2", "k1", "k2", "k3")
    S = c4_spec()
    U, pool, UF, px, nav, crsp, qr, fam = inputs()
    lines = []
    say = lambda s_="": (print(s_), lines.append(s_))
    Tz = pd.read_parquet(CACHE / "target_Tz.parquet")
    R = c4.crsp_pivot(crsp, pool, Tz.index, qr, "ret", px=px)
    PB = pd.read_parquet(CACHE / "pnl_blend.parquet")["pnl"]
    turn_b = json.loads((HERE / f"p1_{STAMP}.json").read_text())["books"]["blend"]["turn"]
    # H2: the z-only spec book's band width that matches the blend's turnover -- band_frontier.match_band_width's
    # bisection, on TURNOVER ONLY, extended visibly to the capped, multiplied spec book (the account's policy)
    f = lambda b: score(book(Tz, S, band=b), R, "z at band")["turn"]
    lo, hi = 0.0005, 0.60          # match_band_width's own bracket (the first run started at the live band and
    #                                the blend turns MORE than z at it, 51.2 vs 48.4, so it raised before any SR)
    tlo, thi = f(lo), f(hi)
    if not (thi <= turn_b <= tlo):
        raise ValueError(f"the blend's turnover {turn_b:.2f} is outside the z book's bracket [{thi:.2f}, {tlo:.2f}]")
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        if f(mid) > turn_b:
            lo = mid
        else:
            hi = mid
    bstar = 0.5 * (lo + hi)
    zr = score(book(Tz, S, band=bstar), R, "z matched")
    rel = abs(zr["turn"] / turn_b - 1)
    if rel > H2_TOL:
        raise ValueError(f"turnover match {rel:.1%} outside the 5% tolerance")
    sr_b = json.loads((HERE / f"p1_{STAMP}.json").read_text())["books"]["blend"]["sr"]
    ok = sr_b > zr["sr"]
    a, b2 = PB.align(zr["P"], join="inner")
    cb = calibrate_block(a.to_numpy(), b2.to_numpy(), candidates=[1, 5, 10, 21, 42], K=1000, M=199, seed=SEED)
    sd = sharpe_diff(a.to_numpy(), b2.to_numpy(), block=int(cb["block"]), M=4999, seed=SEED)
    verdict = "PASS" if ok else "KILL"
    say(f"  blend: gross SR {sr_b:+.3f} at {turn_b:.1f} turns/yr; z-only spec book at band {bstar:.4f} (matched within "
        f"{rel:.1%}): gross SR {zr['sr']:+.3f} at {zr['turn']:.1f}/yr")
    say(f"  sharpe_diff (reported, not gated): block {int(cb['block'])}; " +
        ", ".join(f"{k} {v:.4g}" for k, v in sd.items() if isinstance(v, (int, float))))
    say(f"  rule blend gross SR > matched z-only: {verdict}")
    write("p3", ["CEF trial 54, P3 (H2): matched turnover"] + lines,
          dict(verdict=verdict, sr_blend=sr_b, turn_blend=turn_b, band_star=bstar, sr_z_matched=zr["sr"],
               turn_z_matched=zr["turn"], match_rel=rel, sharpe_diff=sd, block=cb))
    return 0 if ok else 8


def stage_dgl4(impl_root: str) -> int:
    """DG-L4 (§4b): the key absent reproduces C4's v4 book, and the trial's blend reproduces the sleeve's.
    The sleeve is the one on branch c4-level-impl at the commit `impl_root` holds; it is run, never edited,
    through that tree's own fidelity machinery (dgl4_driver.py). Any break stops the trial."""
    import subprocess
    need("dgl2", "p1", "p2", "k1", "k2", "k3", "p3")
    S = c4_spec()
    U, pool, UF, px, nav, crsp, qr, fam = inputs()
    B = level_targets(UF, fam, S, level_mask=None)          # the sleeve has no DG-L3 masks
    CACHE.mkdir(parents=True, exist_ok=True)
    B["Tz"].to_parquet(CACHE / "dgl4_Tz.parquet")
    B["TB"].to_parquet(CACHE / "dgl4_TB_unmasked.parquet")
    root = Path(impl_root)
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()
    out = CACHE / "dgl4_driver.json"
    r = subprocess.run([sys.executable, "-B", str(HERE / "dgl4_driver.py"), str(root), str(CACHE), str(out)],
                       capture_output=True, text=True, cwd=str(root))
    print(r.stdout[-4000:])
    if r.returncode:
        print(r.stderr[-3000:])
        raise RuntimeError("the DG-L4 driver failed")
    j = json.loads(out.read_text())
    a, b = j["a_key_absent"]["report"], j["b_key_present"]["report"]
    ok = a["n_breaks"] == 0 and b["n_breaks"] == 0
    verdict = "CLEAR" if ok else "HALT (a diff: stop and report)"
    lines = [f"CEF trial 54, DG-L4 against the sleeve at {head[:7]} (c4-level-impl): C4 spec {SPEC_ID}",
             *(f"  ({k}) sessions {x['sessions']} ({x['first']}..{x['last']}), matched {x['sessions_matched']}, cells "
               f"{x['cells_matched']}/{x['cells_compared']}, largest gap {x['largest_gap']}, breaks {x['n_breaks']}"
               for k, x in (("a, key absent vs build_book", a), ("b, key present vs the trial's blend", b))),
             *(f"     break {br['date']} {br['kind']}: {br['detail'][:200]}" for br in (a["breaks"] + b["breaks"])[:12]),
             f"  {verdict}"]
    for line in lines:
        print(line)
    write("dgl4", lines, dict(verdict=verdict, sleeve_head=head,
                              a={k: v for k, v in a.items() if k != "rows"}, b={k: v for k, v in b.items() if k != "rows"}))
    return 0 if ok else 9


HOLDOUT_START, HOLDOUT_END = pd.Timestamp("2023-01-03"), pd.Timestamp("2026-09-30")   # §4: C4's own holdout window
HOLDOUT_MARKER = HERE / f"holdout_opened_{STAMP}.txt"
MEANINGFUL_PCT = 0.8      # read_result's "meaningful": §5's lower bound, +0.4%/yr on all capital = 0.8%/yr on C4's
#                           $100k; declared here, before the holdout is opened


def stage_holdout(rehearse: bool = False) -> int:
    """§6.2 step 6, OPENED ONCE: the level book's gross SR > 0 AND the blend's gross return above the z-only book's,
    on 2023-01-03 .. 2026-09-30. Returns as C4's holdout built them (c4_families.holdout): CRSP `ret` to
    2024-12-31 (identity-checked), then the yfinance formula on amendment 4's ruled actions with C4's bar and split
    rulings, and IGR's ruled Alpaca fill. Every book is the declared rule run continuously from 2005; its rows
    through 2022-12-30 are asserted equal to the fit's. The marker is written before any holdout P&L exists."""
    from scripts.cef import w4_artifacts as w4
    from scripts.research.inference import read_result
    need("dgl2", "p1", "p2", "k1", "k2", "k3", "p3", "dgl4")
    # REHEARSAL (C4's precedent): the identical code on fit data, 2021-01-04..2022-12-30; no marker, nothing written
    # beside the trial's files, and no number it prints is a holdout number.
    lo_, hi_ = (pd.Timestamp("2021-01-04"), FIT_END) if rehearse else (HOLDOUT_START, HOLDOUT_END)
    if not rehearse:
        for f in (HOLDOUT_MARKER, HERE / f"holdout_{STAMP}.json", HERE / f"holdout_output_{STAMP}.txt"):
            if f.exists():
                raise RuntimeError(f"the holdout has been opened ({f.name}); it is opened once and never recomputed")
    masks = ruled_masks()
    S = c4_spec()
    U, pool, UF, px, nav, crsp, qr, fam = inputs()
    RT = pd.read_csv(c4.RESOLUTION_TABLE, parse_dates=["date"])
    if (RT["resolved"] == "STOP").any():
        raise RuntimeError("amendment 4 carries an unresolved STOP; C4's holdout returns cannot be built")
    excluded = json.loads(c4.EXCLUSIONS_A4.read_text())["excluded"]
    UH = [t for t in UF if t not in excluded]
    if UH != UF:
        raise RuntimeError(f"C4's holdout excludes {excluded}; this stage was written for an empty exclusion list")
    # C4's holdout's own identity windows (c4_families.holdout): the fit, and the holdout's CRSP leg; each raises
    # naming a failing fund. The rehearsal checks the fit window only (its data end there).
    c4.crsp_identity(crsp, px, UF, c4.SAMPLE_START, FIT_END)
    if not rehearse:
        c4.crsp_identity(crsp, px, UF, HOLDOUT_START, c4.CRSP_END)
    B = level_targets(UH, fam, S, level_mask=masks, end=None if rehearse else HOLDOUT_END)
    sess = B["Tz"].index
    cols = sorted(set(UF) | set(U["snap68"]))
    yfa = pd.read_parquet(c4.FAM_DIR / "cef_actions.parquet")
    yfa["date"] = pd.to_datetime(yfa["date"])
    CACHE.mkdir(parents=True, exist_ok=True)
    act = CACHE / "holdout_actions_ruled.parquet"
    c4.ruled_actions(yfa, RT, excluded).to_parquet(act, index=False)
    cr = c4.crsp_pivot(crsp, cols, sess, qr, "ret", px=px)
    # IGR's ruled fill (C4's holdout ruling 2026-10-14: Alpaca's split-adjusted closes on 2026-09-08/09). The real
    # run applies it and says so; the rehearsal's window ends 2022-12-30, so it cannot hold those dates, and it
    # says that it skips them. Neither path is silent.
    if rehearse:
        fill = {}
        pre_notes = [f"  IGR fill: SKIPPED in the rehearsal (its dates {', '.join(str(d.date()) for d in c4.IGR_FILL)} are "
                     f"outside 2021-01-04..2022-12-30); the real holdout run applies it"]
    else:
        fill = c4.igr_fill(c4.alpaca_pool(), px, sess)[0]
        if sorted(fill) != sorted(c4.IGR_FILL) or not all(d in sess for d in fill):
            raise RuntimeError(f"IGR fill dates {sorted(fill)} are not C4's ruled {c4.IGR_FILL} inside the session index")
        pre_notes = ["  IGR fill APPLIED (C4's ruling 2026-10-14, Alpaca split-adjusted): " +
                     ", ".join(f"{d.date()} {v:+.4%}" for d, v in sorted(fill.items()))]
    for n_ in pre_notes:
        print(n_)
    yf = c4.yf_total_returns(px, cols, sess, actions=act, rulings=c4.BAR_RULINGS, split_rulings=c4.SPLIT_RULINGS)
    for d, v in fill.items():
        if rehearse and d not in yf.index:
            continue
        if pd.notna(yf.loc[d, "IGR"]):
            raise RuntimeError(f"IGR {d.date()} already has a yfinance return; the ruled fill does not apply")
        yf.loc[d, "IGR"] = v
    R = pd.concat([cr.loc[:c4.CRSP_END], yf.loc[c4.YF_START:]])
    if not R.index.equals(sess):
        raise RuntimeError("the CRSP and yfinance legs do not tile the session index at the seam")
    head = __import__("subprocess").run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True,
                                        text=True, check=True).stdout.strip()
    if rehearse:
        print("REHEARSAL on fit data 2021-01-04..2022-12-30: not the holdout")
    else:
        HOLDOUT_MARKER.write_text(f"CEF trial 54 holdout opened {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} "
                                  f"at commit {head} by `trial54.py holdout`. Opened once; this file makes a second run refuse.\n")
    # ---- holdout P&L exists from here
    lines = list(pre_notes)
    say = lambda s_="": (print(s_), lines.append(s_))
    fitj = json.loads((HERE / f"p1_{STAMP}.json").read_text())["books"]
    out = {"commit": head, "window": [str(HOLDOUT_START.date()), str(HOLDOUT_END.date())], "books": {},
           "igr_fill": {str(d.date()): float(v) for d, v in fill.items()}, "rehearsal": rehearse}
    pn = {}
    for k, T in (("z", B["Tz"]), ("level", B["TL"]), ("blend", B["TB"])):
        H = book(T, S)
        Hfit = book(T.loc[:FIT_END], S)
        if not np.array_equal(H.loc[:FIT_END].to_numpy(), Hfit.to_numpy()):
            raise AssertionError(f"the {k} book's rows through 2022-12-30 are not the fit's")
        R0 = c4.check_held(H, R.reindex(H.index)[H.columns], f"{k} holdout")
        res = bf.evaluate(H, R0)
        fitP = res["pnl"].loc[pd.Timestamp(fitj[k]["first_held"]):FIT_END]
        if abs(c4.sr_of(fitP) - fitj[k]["sr"]) > 1e-9:
            raise AssertionError(f"the {k} book's fit P&L does not reproduce P1's ({c4.sr_of(fitP):.6f} vs {fitj[k]['sr']:.6f})")
        P, TU = res["pnl"].loc[lo_:hi_], res["turn_series"].loc[lo_:hi_]
        if rehearse and P.index.max() > FIT_END:
            raise AssertionError("the rehearsal formed a P&L row after 2022-12-30")
        st = c4.row_stats(P, TU)
        eras = {lab: c4.row_stats(P.loc[a:b], TU.loc[a:b]) for lab, a, b in
                ((("2021", "2021-01-01", "2021-12-31"), ("2022", "2022-01-01", "2022-12-31")) if rehearse else
                 (("2023-24", "2023-01-01", "2024-12-31"), ("2025-26", "2025-01-01", "2026-09-30")))}
        out["books"][k] = dict(**st, eras=eras)
        pn[k] = P
        say(f"  {k:<6} holdout: gross SR {st['sr']:+.3f}  ann {st['ann_pct']:+.2f}%  vol {st['vol_pct']:.2f}%  turn {st['turn']:.1f}/yr  "
            f"net @5/15/30 {st['net5']:+.3f} / {st['net15']:+.3f} / {st['net30']:+.3f}  flips {st['flips']};  "
            + "; ".join(f"{e} SR {v['sr']:+.2f} ann {v['ann_pct']:+.2f}%" for e, v in eras.items()))
    bz, bl, bb = out["books"]["z"], out["books"]["level"], out["books"]["blend"]
    ok = bl["sr"] > 0 and bb["ann_pct"] > bz["ann_pct"]
    verdict = "PASS" if ok else "KILL (D3)"
    d2 = bb["net15"] >= bz["net15"]
    y, x = pn["level"], pn["z"]
    f0, _ = _hac_alpha(y, x, 0)
    L = w4.nw_auto_lag(f0.resid)
    f, d = _hac_alpha(y, x, L)
    a_pct, se_pct = float(f.params["const"]) * 252 * 100, float(f.bse["const"]) * 252 * 100
    ev = read_result(a_pct, se_pct, MEANINGFUL_PCT, n_trials=54)
    out.update(verdict=verdict, d2_label=(not d2), level_alpha_on_z=dict(alpha_pct=a_pct, se_pct=se_pct,
               t=float(f.tvalues["const"]), lag=L), evidence=ev)
    say(f"  rule: level gross SR {bl['sr']:+.3f} > 0 AND blend ann {bb['ann_pct']:+.2f}% > z-only ann {bz['ann_pct']:+.2f}%: {verdict}")
    say(f"  net at 15bp: blend {bb['net15']:+.3f} vs z-only {bz['net15']:+.3f} -> {'no D2' if d2 else 'D2 label'}")
    say(f"  evidence (report): level-on-z alpha {a_pct:+.2f}%/yr, SE {se_pct:.2f}, NW t {float(f.tvalues['const']):.2f} (lag {L}); "
        f"read_result at N 54, meaningful {MEANINGFUL_PCT}%/yr: {ev.get('outcome', ev)}")
    if rehearse:
        (CACHE / "holdout_REHEARSAL.txt").write_text("\n".join(lines) + "\n")
        return 0
    write("holdout", [f"CEF trial 54 HOLDOUT, opened ONCE ({HOLDOUT_START.date()}..{HOLDOUT_END.date()}), commit {head}; "
                      f"C4 spec {SPEC_ID}, m {S['m']}, cap {S['cap']}; CRSP ret to 2024-12-31, yfinance ruled leg from 2025"]
          + lines, out)
    return 0 if ok else 10


NAV_JUMP, NAV_BACK, NAV_RUN, PX_FLAT = 0.05, 0.01, 3, 0.02


def nav_misprints(nav: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    """A PROPOSED rule for the team lead (no P&L): a NAV misprint is a run of 1..NAV_RUN sessions whose NAV
    differs from the session before the run by >= NAV_JUMP, after which the NAV comes back within NAV_BACK of
    that prior NAV, while the close stays within PX_FLAT of its prior close on every day of the run (the
    market did not move; the vendor's NAV did). Returns one row per misprinted name-day."""
    out = []
    for t in nav.columns:
        n, c = nav[t].to_numpy(), close[t].reindex(nav.index).to_numpy()
        i = 1
        while i < len(n) - 1:
            if not (np.isfinite(n[i - 1]) and np.isfinite(n[i]) and n[i - 1] > 0):
                i += 1; continue
            base, cb = n[i - 1], c[i - 1]
            if abs(n[i] / base - 1) < NAV_JUMP:
                i += 1; continue
            for L in range(1, NAV_RUN + 1):
                j = i + L
                if j >= len(n) or not np.isfinite(n[j]):
                    break
                if abs(n[j] / base - 1) <= NAV_BACK:
                    run = range(i, j)
                    flat = all(np.isfinite(c[k]) and np.isfinite(cb) and abs(c[k] / cb - 1) < PX_FLAT for k in run)
                    if flat and all(abs(n[k] / base - 1) >= NAV_JUMP for k in run):
                        out += [dict(ticker=t, date=nav.index[k].date().isoformat(), nav_prior=float(base),
                                     nav=float(n[k]), nav_after=float(n[j]), run_len=L) for k in run]
                    break
            i += 1
    return pd.DataFrame(out, columns=["ticker", "date", "nav_prior", "nav", "nav_after", "run_len"])


def stage_navscan() -> int:
    lines = []
    say = lambda s="": (print(s), lines.append(s))
    U, pool, UF, px, nav, crsp, qr, fam = inputs()
    nv = nav.pivot_table(index="date", columns="ticker", values="nav").sort_index()
    cl = px.pivot_table(index="date", columns="ticker", values="close").sort_index()
    nv = nv.loc[:FIT_END, [t for t in UF if t in nv.columns]]
    M = nav_misprints(nv, cl)
    M = M[pd.to_datetime(M.date) >= pd.Timestamp("2004-01-01")]
    M.to_csv(HERE / f"nav_misprints_PROPOSED_{STAMP}.csv", index=False)
    F = pd.read_csv(HERE / f"dgl3_flags_{STAMP}.csv")
    keyF = set(zip(F.ticker, F.date))
    nxt = {}
    for t, g in F.groupby("ticker"):
        pass
    say(f"CEF trial 54, NAV-misprint scan ({STAMP}; no P&L): rule = NAV jumps >= {NAV_JUMP:.0%} for 1..{NAV_RUN} sessions "
        f"and returns within {NAV_BACK:.0%} of the prior NAV, the close within {PX_FLAT:.0%} of its prior close throughout")
    say(f"  the frozen 74's families NAVs, 2004-01-01..{FIT_END.date()}: {len(M)} misprinted name-days in "
        f"{M.groupby(['ticker', 'nav_prior']).ngroups if len(M) else 0} runs, {M.ticker.nunique() if len(M) else 0} funds")
    say(f"  of them among the 242 DG-L3 flags: {sum((t, d) in keyF for t, d in zip(M.ticker, M.date))}; "
        f"the rest were below the 10% flag line or on days whose price TR moved with the NAV")
    say("  by year: " + str(pd.to_datetime(M.date).dt.year.value_counts().sort_index().to_dict() if len(M) else {}))
    for _, r in M.head(40).iterrows():
        say(f"    {r.ticker} {r.date}: NAV {r.nav_prior:.2f} -> {r.nav:.2f} -> {r.nav_after:.2f} (run {r.run_len})")
    (HERE / f"navscan_output_{STAMP}.txt").write_text("\n".join(lines) + "\n")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["dgl2", "dgl3", "navscan", "p1", "record", "p2", "k1", "k2", "k3", "p3", "dgl4", "holdout"])
    ap.add_argument("--variant", choices=["blend", "level", "z", "blend_corrected", "level_corrected"], default=None)
    ap.add_argument("--impl-root", default=None, help="dgl4: a checkout of c4-level-impl at its code commit")
    ap.add_argument("--rehearse", action="store_true", help="holdout: the identical code on fit data 2021-22")
    a = ap.parse_args(argv)
    if a.stage == "dgl4":
        if not a.impl_root:
            raise SystemExit("dgl4 needs --impl-root")
        return stage_dgl4(a.impl_root)
    if a.stage == "record":
        if a.variant is None:
            raise SystemExit("record needs --variant")
        return stage_record(a.variant)
    return {"dgl2": stage_dgl2, "dgl3": stage_dgl3, "navscan": stage_navscan, "p1": stage_p1, "p2": stage_p2,
            "k1": stage_k1, "k2": stage_k2, "k3": stage_k3, "p3": stage_p3,
            "holdout": lambda: stage_holdout(a.rehearse)}[a.stage]()


if __name__ == "__main__":
    raise SystemExit(main())
