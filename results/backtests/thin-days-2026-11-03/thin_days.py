"""Thin sessions: the harness's HOLD rule against the live sleeve's FLATTEN rule (report only, 2026-11-03).

ZERO TRIALS, NO SPEC CHANGE. Every book is the canonical path:
`band_frontier.build_targets` -> `band_gross_capped` -> `evaluate` (shift(2):
decide t, fill t+1, earn t+2), total returns (`total_returns`), the spec read
through `scripts/cef/spec.py`. The only new harness code is
`band_gross_capped(below_min_names=, thin=)` and `thin_sessions`
(no-op proof: noop_before.txt / noop_after.txt in this folder).

THE TWO RULES on a decision date with fewer than `min_names` eligible names:
  hold     the harness default: `build_targets` carries the previous target and
           the band and ceiling act on it as on any day;
  flatten  the live sleeve (src/deploy/sleeves/cef_discount.py l.892-895, no
           `below_min_names` key in the spec, `registry.cef_below_min_names`
           -> "flatten"): every name to zero, then the band reopens from flat.
Each crossed with the flip handling: instant (the harness) and deferred
(`defer_flips=True`, quantt/session/decide.py FLIP_SAME_SESSION=False, which
is how the live runner trades).

RETURNS are cut at the last distribution ex-date of any universe name
(DIST_END), as the turnover study did: `total_returns` does not raise when the
distribution panel ends before the price panel, so a later return would
silently miss a distribution. Each name's next expected ex-date (last ex-date +
its median gap over its last 12 gaps) is asserted to fall after DIST_END.

SECOND METHODS, all asserted, none optional:
  * the thin-session set equals the LIVE SLEEVE's own answer on every decision
    date (sleeve_thin.csv, from sleeve_thin_check.py), and so does the count;
  * the flatten books equal an independently written pandas loop;
  * `scripts.research.harness.report` (nan_policy="raise") reproduces the fit
    and holdout rows of the flatten instant book.

REVIEW FIXES (2026-11-03, after the review, the re-derivation and the
beta-detector pass): the "[days]" count of the flatten-minus-hold split no
longer counts NaN != NaN on the first two rows (974 / 977, not 976 / 979, in
the fit period); step 5 adds trial 53's book as activated in the newest release
tag (sizing_multiplier read from that tag's frozen spec) under both rules, with
the hold row asserted equal to trial 53's committed figures. The attacks on
hold's extra return are in attack.py beside this file.

    python3 results/backtests/thin-days-2026-11-03/thin_days.py     # about 1-2 min

Writes run.log and results.json beside this file. Reads data/ only.
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]          # the worktree root
sys.path.insert(0, str(REPO))

import numpy as np                                    # noqa: E402
import pandas as pd                                   # noqa: E402

from scripts.cef import band_frontier as bf           # noqa: E402
from scripts.cef.spec import (BAND_WIDTH, MAX_GROSS_STRESS, MIN_ADV_USD,   # noqa: E402
                              MIN_NAMES, SPEC_ID, UNIVERSE, VOL_TARGET, spec)
from scripts.research.harness import ERAS, HOLDOUT_START, report   # noqa: E402
from scripts.research.inference import newey_west_t   # noqa: E402
from src.deploy.registry import cef_below_min_names   # noqa: E402

COSTS = (5, 15, 30)
P = 252
LOG = []
OUT = {}


def p(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    LOG.append(s)


def pct(x, d=2):
    return "n/a" if x is None or not np.isfinite(x) else f"{x * 100:.{d}f}"


# --------------------------------------------------------------------------- inputs
def load():
    T, R = bf.build_targets()
    thin = bf.thin_sessions(T.index)
    panel = bf.build_panel()
    # second method 1: the live sleeve's own answer, date by date
    s = pd.read_csv(HERE / "sleeve_thin.csv", parse_dates=["date"]).set_index("date")
    if not s.index.equals(T.index):
        raise AssertionError("sleeve_thin.csv is not on build_targets' index; re-run sleeve_thin_check.py")
    if not (s["thin"].to_numpy() == thin.to_numpy()).all():
        bad = s.index[s["thin"].to_numpy() != thin.to_numpy()]
        raise AssertionError(f"thin_sessions and the live sleeve disagree on {len(bad)} dates, first {bad[0].date()}")
    ok = panel["z"].reindex(T.index).notna() & (panel["adv"].reindex(T.index) >= MIN_ADV_USD)
    cnt = ok.sum(axis=1)
    m = s["thin"].to_numpy()
    if not (s["n_eligible"].to_numpy()[m] == cnt.to_numpy()[m]).all():
        raise AssertionError("the sleeve's eligible count differs from the harness's on a thin date")
    nav_drops = int((s["nav_drop_names"].fillna("") != "").sum())
    p(f"second method 1 [live sleeve on {len(s)} decision dates]: thin set identical "
      f"({int(thin.sum())} thin), eligible count identical on every thin date, "
      f"dates where the sleeve dropped a name for a stale or missing NAV: {nav_drops}")
    OUT["sleeve_check"] = dict(dates=len(s), thin=int(thin.sum()), nav_drop_dates=nav_drops)

    dist = pd.read_parquet(bf.DATA_DIR / "cef_distributions.parquet")
    dist["ex_date"] = pd.to_datetime(dist["ex_date"])
    du = dist[dist.ticker.isin(UNIVERSE)]
    dist_end = du["ex_date"].max()
    # F4 of the turnover study: each name's next expected ex-date must fall after DIST_END
    nxt = {}
    for tk, g in du.groupby("ticker"):
        d = g["ex_date"].sort_values().drop_duplicates()
        gap = d.diff().dropna().tail(12).median()
        nxt[tk] = (d.iloc[-1], d.iloc[-1] + gap)
        if not d.iloc[-1] + gap > dist_end:
            raise AssertionError(f"{tk}: last ex-date {d.iloc[-1].date()}, median gap {gap.days}d, so a "
                                 f"distribution was due by {dist_end.date()} and is missing")
    p(f"DIST_END {dist_end.date()}; every name's next expected ex-date is after it "
      f"(earliest {min(v[1] for v in nxt.values()).date()})")
    keep = T.index <= dist_end
    Rt = bf.total_returns(R.loc[keep])
    return T, R, thin, panel, dist_end, keep, Rt


def books(T, thin):
    cap = MAX_GROSS_STRESS
    H = {}
    for rule in ("hold", "flatten"):
        kw = {} if rule == "hold" else dict(below_min_names="flatten", thin=thin)
        H[(rule, "instant")] = bf.band_gross_capped(T, BAND_WIDTH, cap, **kw)
        H[(rule, "deferred")] = bf.band_gross_capped(T, BAND_WIDTH, cap, defer_flips=True, **kw)
    return H


def independent_flatten(T, thin, defer):
    """Second method 2: the live rule written again, row by row in pandas, with
    the ceiling as `f = cap / gross` inline (not `_cap_gross`)."""
    cap, b = MAX_GROSS_STRESS, BAND_WIDTH
    prev = pd.Series(0.0, index=T.columns)
    rows = []
    for d in T.index:
        if thin.loc[d]:
            now = prev * 0.0
        else:
            tgt = T.loc[d]
            now = prev.copy()
            out = (tgt - prev).abs() > b
            now[out] = tgt[out] - np.sign((tgt - prev)[out]) * b
            g = now.abs().sum()
            if g > cap:
                now = now * (cap / g)
            if defer:
                now[(prev * now) < 0] = 0.0
        rows.append(now.values)
        prev = now
    return pd.DataFrame(rows, index=T.index, columns=T.columns)


# --------------------------------------------------------------------------- statistics
def windows(dist_end):
    w = [(("2023+" if lab == "2023-" else lab), pd.Timestamp(a), pd.Timestamp(b) if b else dist_end)
         for lab, a, b in ERAS]
    w += [("FIT <2023", pd.Timestamp(bf.SAMPLE_START), HOLDOUT_START - pd.Timedelta(days=1)),
          ("H13 2023+", HOLDOUT_START, dist_end),
          ("full", pd.Timestamp(bf.SAMPLE_START), dist_end)]
    return w


def stats(pnl, turn):
    ann, vol, tu = pnl.mean() * P, pnl.std() * np.sqrt(P), turn.mean() * P
    eq = (1 + pnl).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    out = dict(n=int(len(pnl)), ann=float(ann), vol=float(vol), turn=float(tu), maxdd=dd)
    if vol == 0:
        out.update(flat=True)
        return out
    nets = {c: ann - tu * c / 1e4 for c in COSTS}
    flip = next((c for c in COSTS if np.sign(nets[c]) != np.sign(ann)), None)
    k = VOL_TARGET / vol                      # descriptive: realised (ex-post) vol
    out.update(flat=False, sr=float(ann / vol), net={c: float(v) for c, v in nets.items()},
               net_sr={c: float(nets[c] / vol) for c in COSTS},
               be=float(ann / tu * 1e4) if tu > 0 else float("nan"), flip_bp=flip,
               vm=dict(scale=float(k), ann=float(ann * k), turn=float(tu * k),
                       net={c: float(nets[c] * k) for c in COSTS}))
    return out


def table(res, H, Rt, dist_end):
    """Step 3: rule x flips x window. The A2 window (2013-06-14 on, the alpha-leakage note's
    deferred-flip window) is added as a context row for the turnover study's open F3."""
    W = windows(dist_end) + [("A2 2013-06-14+", pd.Timestamp("2013-06-14"), dist_end)]
    rows = {}
    for key, h in H.items():
        r = res[key]
        for lab, a, b in W:
            rows[(key, lab)] = stats(r["pnl"].loc[a:b], r["turn_series"].loc[a:b])
    p("\n=== STEP 3: both rules x {instant, deferred}; total return, gross headline; cost grid beside "
      "(real-money view, labelled); no borrow charged ===")
    p(f"{'window':<15}{'rule':<9}{'flips':<9}{'SR':>6}{'ann%':>7}{'vol%':>6}{'maxDD%':>8}{'turn/yr':>8} | "
      f"{'net%/yr @5 / @15 / @30':>24} | {'netSR @5 / @15 / @30':>20} | {'BE bp':>6} {'flip?':>6}")
    for lab, a, b in W:
        for key in H:
            s = rows[(key, lab)]
            if s["flat"]:
                p(f"{lab:<15}{key[0]:<9}{key[1]:<9} flat: held nothing (turn {s['turn']:.1f})")
                continue
            nets = " / ".join(f"{s['net'][c] * 100:6.2f}" for c in COSTS)
            nsr = " / ".join(f"{s['net_sr'][c]:5.2f}" for c in COSTS)
            fl = f"{s['flip_bp']}bp" if s["flip_bp"] else "no"
            p(f"{lab:<15}{key[0]:<9}{key[1]:<9}{s['sr']:6.2f}{s['ann'] * 100:7.2f}{s['vol'] * 100:6.2f}"
              f"{s['maxdd'] * 100:8.1f}{s['turn']:8.1f} | {nets:>24} | {nsr:>20} | {s['be']:6.1f} {fl:>6}")
    p("\n--- vol-matched view: each book scaled to the spec's vol_target_annual "
      f"({VOL_TARGET:.0%}) on its OWN REALISED vol in that window (ex post, so descriptive only) ---")
    p(f"{'window':<15}{'rule':<9}{'flips':<9}{'scale':>6}{'ann%@6':>8}{'turn@6':>8} | net%/yr @5 / @15 / @30")
    for lab, a, b in W:
        for key in H:
            s = rows[(key, lab)]
            if s["flat"]:
                continue
            v = s["vm"]
            p(f"{lab:<15}{key[0]:<9}{key[1]:<9}{v['scale']:6.2f}{v['ann'] * 100:8.2f}{v['turn']:8.1f} | "
              + " / ".join(f"{v['net'][c] * 100:6.2f}" for c in COSTS))
    p("\n--- era turnover sd/mean (H5): sd (ddof=1) over the five eras' turn/yr, and over the four "
      "traded eras (2005-09 holds nothing under either rule) ---")
    era_labs = [("2023+" if lab == "2023-" else lab) for lab, _, _ in ERAS]
    cv = {}
    for key in H:
        t5 = np.array([rows[(key, e)]["turn"] for e in era_labs])
        t4 = t5[1:]
        cv[f"{key[0]}/{key[1]}"] = dict(eras=[float(x) for x in t5], cv5=float(t5.std(ddof=1) / t5.mean()),
                                        cv4=float(t4.std(ddof=1) / t4.mean()))
        p(f"{key[0]:<9}{key[1]:<9} turn/yr by era {' / '.join(f'{x:.1f}' for x in t5)}  "
          f"sd/mean five {cv[f'{key[0]}/{key[1]}']['cv5']:.2f}, four traded {cv[f'{key[0]}/{key[1]}']['cv4']:.2f}")
    OUT["table"] = {f"{k[0][0]}/{k[0][1]}/{k[1]}": v for k, v in rows.items()}
    OUT["turnover_cv"] = cv

    p("\n--- paired daily difference, same windows: hold minus flatten (same flip mode), and "
      "deferred minus instant (same rule); NW t (Bartlett, Newey-West 1994 lag) ---")
    p(f"{'window':<15}{'hold-flat inst':>16}{'t':>6}{'hold-flat def':>15}{'t':>6}"
      f"{'def-inst hold':>15}{'t':>6}{'def-inst flat':>15}{'t':>6}   (pp/yr)")
    diffs = {}
    for lab, a, b in W:
        cells = []
        for x, y in ((("hold", "instant"), ("flatten", "instant")), (("hold", "deferred"), ("flatten", "deferred")),
                     (("hold", "deferred"), ("hold", "instant")), (("flatten", "deferred"), ("flatten", "instant"))):
            d = (res[x]["pnl"] - res[y]["pnl"]).loc[a:b]
            if (d == 0).all():
                cells.append((0.0, float("nan")))
            else:
                cells.append((float(d.mean() * P), float(newey_west_t(d.to_numpy()))))
        diffs[lab] = cells
        p(f"{lab:<15}" + "".join(f"{c[0] * 100:16.2f}{c[1]:6.2f}" if i == 0 else f"{c[0] * 100:15.2f}{c[1]:6.2f}"
                                 for i, c in enumerate(cells)))
    OUT["paired"] = diffs
    return rows


# --------------------------------------------------------------------------- step 4
def categories(T, panel):
    """The eligibility test each name fails on each decision date, in the
    sleeve's order (target_positions l.795-839): z first, then ADV unmeasured,
    then ADV below the floor. A name that passes all of them is 'eligible'
    (it can sit in a thin session because the cross-section is short)."""
    z = panel["z"].reindex(T.index)[UNIVERSE]
    adv = panel["adv"].reindex(T.index)[UNIVERSE]
    disc = panel["disc"].reindex(T.index)[UNIVERSE]
    mu = panel["mu"].reindex(T.index)[UNIVERSE]
    c = pd.DataFrame("eligible", index=T.index, columns=UNIVERSE, dtype=object)
    c = c.mask(adv.notna() & (adv < MIN_ADV_USD), "ADV below floor")
    c = c.mask(adv.isna(), "ADV unmeasured")
    noz = z.isna()
    c = c.mask(noz & disc.isna(), "no z: no paired price/NAV row")
    c = c.mask(noz & disc.notna() & mu.isna(), "no z: under 120 obs in window")
    c = c.mask(noz & disc.notna() & mu.notna(), "no z: other")
    return c


def run_age(thin):
    """Sessions since the last active decision, 1 on the first thin session of a run, 0 when active."""
    a, n = [], 0
    for v in thin.to_numpy():
        n = n + 1 if v else 0
        a.append(n)
    return pd.Series(a, index=thin.index)


def step4(H, res, Rt, thin, panel, dist_end, T):
    W = [w for w in windows(dist_end) if w[0] not in ("2005-09", "full")]
    cat = categories(T, panel)
    Hh = H[("hold", "instant")]
    held = Hh.shift(2).reindex(Rt.index).fillna(0.0)        # H1: decided t earns t+2
    C = held * Rt
    if not np.allclose(C.sum(axis=1).to_numpy(), res[("hold", "instant")]["pnl"].to_numpy(), atol=1e-15):
        raise AssertionError("name-day attribution does not sum to evaluate()'s P&L")
    thin_d = thin.shift(2).reindex(Rt.index)
    thin_d = thin_d.where(thin_d.notna(), False).astype(bool)   # the first two rows earn nothing
    cat_d = cat.shift(2).reindex(Rt.index)
    age_d = run_age(thin).shift(2).reindex(Rt.index).fillna(0)
    ret_raw = panel["ret"].reindex(Rt.index)[UNIVERSE]           # NaN where build_targets zero-fills
    volu = panel["vol"].reindex(Rt.index)[UNIVERSE]
    isheld = held != 0
    out = {}

    p("\n=== STEP 4: where the hold book's thin-session P&L comes from (hold, instant flips) ===")
    p("Attribution: P&L on earning day d by name = H[d-2] x R[d] (evaluate()'s own product, asserted to sum "
      "to its P&L); a day is 'thin' when its decision d-2 was a thin session. ann% = sum / days in window x 252.")
    g = Hh.abs().sum(axis=1)
    p(f"\n{'window':<10}{'days':>6}{'thin dec':>9}{'ann% all':>9}{'ann% thin':>10}{'ann% active':>12}"
      f"{'gross thin':>11}{'gross active':>13}")
    for lab, a, b in W:
        x, m = res[("hold", "instant")]["pnl"].loc[a:b], thin_d.loc[a:b]
        dec = thin.loc[a:b]
        gw = g.loc[a:b]
        row = dict(days=int(len(x)), thin_dec=int(dec.sum()), ann=float(x.mean() * P),
                   ann_thin=float(x[m].sum() / len(x) * P), ann_active=float(x[~m].sum() / len(x) * P),
                   gross_thin=float(gw[dec].mean()) if dec.any() else float("nan"),
                   gross_active=float(gw[~dec].mean()))
        out.setdefault("split", {})[lab] = row
        p(f"{lab:<10}{row['days']:6d}{row['thin_dec']:9d}{pct(row['ann']):>9}{pct(row['ann_thin']):>10}"
          f"{pct(row['ann_active']):>12}{row['gross_thin']:11.2f}{row['gross_active']:13.2f}")

    labels = ["eligible", "ADV below floor", "ADV unmeasured", "no z: no paired price/NAV row",
              "no z: under 120 obs in window", "no z: other"]
    p("\n--- thin-session P&L by the test the HELD name failed at the decision (ann% of the window; "
      "[held name-days]) ---")
    p("Stale NAV (`max_nav_age_bd`): cannot bind behind a finite z (the sleeve's nav is the same inner join), "
      "and the sleeve's own run dropped no name for it on any date (second method 1).")
    p(f"{'window':<10}" + "".join(f"{l[:24]:>26}" for l in labels))
    for lab, a, b in W:
        m = thin_d.loc[a:b]
        cc, kk, hh = C.loc[a:b][m], cat_d.loc[a:b][m], isheld.loc[a:b][m]
        n = len(C.loc[a:b])
        cells = {}
        for l in labels:
            sel = (kk == l) & hh
            cells[l] = dict(ann=float(cc[sel].sum().sum() / n * P), n=int(sel.sum().sum()))
        out.setdefault("by_test", {})[lab] = cells
        p(f"{lab:<10}" + "".join(f"{pct(cells[l]['ann']):>16} [{cells[l]['n']:>6}]" for l in labels))

    p("\n--- thin-session P&L by name (ann% of the window), hold instant ---")
    p(f"{'name':<6}" + "".join(f"{lab:>11}" for lab, _, _ in W))
    byname = {}
    for tk in UNIVERSE:
        vals = []
        for lab, a, b in W:
            m = thin_d.loc[a:b]
            vals.append(float(C.loc[a:b][m][tk].sum() / len(C.loc[a:b]) * P))
        byname[tk] = vals
        p(f"{tk:<6}" + "".join(f"{pct(v):>11}" for v in vals))
    out["by_name"] = {tk: dict(zip([w[0] for w in W], v)) for tk, v in byname.items()}

    p("\n--- stale-price signature on HELD name-days: thin-decision days vs active-decision days ---")
    p("zero R = the harness return is exactly 0 (of which: zero-filled = no price return that day, "
      "the gap is dropped, not deferred; repeated close = ret exactly 0); vol0 = volume 0 that day; "
      "catch-up = first non-zero return after a zero one, and the P&L earned on such held name-days "
      "(ann% of the window)")
    p(f"{'window':<10}{'set':<8}{'name-days':>10}{'zero R%':>8}{'z-fill%':>8}{'rep cl%':>8}{'vol0%':>7}"
      f"{'catchup%':>9}{'catch-up P&L ann%':>19}")
    zero = Rt[UNIVERSE] == 0
    zfill = ret_raw.isna()
    rep = ret_raw == 0
    v0 = volu == 0
    catch = (Rt[UNIVERSE] != 0) & (Rt[UNIVERSE].shift(1) == 0)
    for lab, a, b in W:
        for nm, msk in (("thin", thin_d.loc[a:b]), ("active", ~thin_d.loc[a:b])):
            h = isheld.loc[a:b][msk]
            nd = int(h.sum().sum())
            if nd == 0:
                p(f"{lab:<10}{nm:<8}{0:10d}")
                continue
            f = lambda X: float((X.loc[a:b][msk] & h).sum().sum() / nd)     # noqa: E731
            cc = C.loc[a:b][msk]
            share = float(cc.where(catch.loc[a:b][msk] & h, 0.0).sum().sum() / len(C.loc[a:b]) * P)
            row = dict(n=nd, zero=f(zero), zfill=f(zfill), rep=f(rep), vol0=f(v0), catch=f(catch), pnl_catch=share)
            out.setdefault("stale", {}).setdefault(lab, {})[nm] = row
            p(f"{lab:<10}{nm:<8}{nd:10d}{row['zero'] * 100:8.2f}{row['zfill'] * 100:8.2f}{row['rep'] * 100:8.2f}"
              f"{row['vol0'] * 100:7.2f}{row['catch'] * 100:9.2f}{share * 100:19.2f}")

    p("\n--- thin-session P&L by age of the held book within its thin run (sessions since the last "
      "active decision), hold instant, ann% of the window ---")
    buckets = [(1, 5), (6, 21), (22, 63), (64, 10 ** 6)]
    p(f"{'window':<10}" + "".join(f"{f'{lo}-{hi}' if hi < 10 ** 6 else f'{lo}+':>14}" for lo, hi in buckets))
    pnl_h = res[("hold", "instant")]["pnl"]
    for lab, a, b in W:
        x, ag = pnl_h.loc[a:b], age_d.loc[a:b]
        cells = [(float(x[(ag >= lo) & (ag <= hi)].sum() / len(x) * P), int(((ag >= lo) & (ag <= hi)).sum()))
                 for lo, hi in buckets]
        out.setdefault("by_age", {})[lab] = cells
        p(f"{lab:<10}" + "".join(f"{pct(c[0]):>8} [{c[1]:>4}]" for c in cells))

    grp = pd.read_parquet(bf.DATA_DIR / "cef_prices.parquet", columns=["ticker", "grp"]).drop_duplicates()
    grp = grp[grp.ticker.isin(UNIVERSE)].set_index("ticker")["grp"]
    if grp.index.duplicated().any() or set(grp.index) != set(UNIVERSE):
        raise AssertionError("the price panel's grp column is not one value per universe name")
    gl = sorted(grp.unique())
    p("\n--- mean signed weight held by mandate group (price panel `grp`), thin vs active decisions, hold instant ---")
    p(f"{'window':<10}{'set':<8}" + "".join(f"{x:>8}" for x in gl) + f"{'net':>8}")
    for lab, a, b in W:
        dec = thin.loc[a:b]
        for nm, msk in (("thin", dec), ("active", ~dec)):
            if not msk.any():
                continue
            hw = Hh.loc[a:b][msk]
            gw = {x: float(hw[grp.index[grp == x]].sum(axis=1).mean()) for x in gl}
            out.setdefault("groups", {}).setdefault(lab, {})[nm] = gw
            p(f"{lab:<10}{nm:<8}" + "".join(f"{gw[x]:8.3f}" for x in gl) + f"{hw.sum(axis=1).mean():8.3f}")

    # ---- attacks on the thin-session P&L (added before reading any of their output)
    y = bf.distribution_yield(Rt.index, Rt.columns).reindex_like(Rt)[UNIVERSE]
    Cd = held[UNIVERSE] * y
    ew = Rt[UNIVERSE].where(ret_raw.notna()).mean(axis=1)    # equal-weight universe total return, names that printed
    p("\n--- attack 1: thin-session P&L split into the price leg and the distribution leg (ann% of the window), "
      "and regressed on the equal-weight universe total return on the same days (thin-decision days only) ---")
    p(f"{'window':<10}{'thin ann%':>10}{'price':>8}{'dist':>8}{'beta':>7}{'beta part':>10}{'alpha part':>11}{'NW t(alpha)':>12}")
    for lab, a, b in W:
        m = thin_d.loc[a:b]
        n = len(C.loc[a:b])
        tot = float(C.loc[a:b][m].sum().sum() / n * P)
        dist_ = float(Cd.loc[a:b][m].sum().sum() / n * P)
        yv, xv = res[("hold", "instant")]["pnl"].loc[a:b][m], ew.loc[a:b][m]
        ok = xv.notna()
        yv, xv = yv[ok], xv[ok]
        if len(yv) > 30 and xv.var() > 0:
            beta = float(np.cov(yv, xv, ddof=1)[0, 1] / xv.var(ddof=1))
            resid = yv - beta * xv
            bpart, apart = float(beta * xv.sum() / n * P), float(resid.sum() / n * P)
            ta = float(newey_west_t(resid.to_numpy()))
        else:
            beta = bpart = apart = ta = float("nan")
        out.setdefault("legs_beta", {})[lab] = dict(thin=tot, price=tot - dist_, dist=dist_, beta=beta,
                                                    beta_part=bpart, alpha_part=apart, t_alpha=ta)
        p(f"{lab:<10}{pct(tot):>10}{pct(tot - dist_):>8}{pct(dist_):>8}{beta:7.3f}{pct(bpart):>10}{pct(apart):>11}{ta:12.2f}")

    lags = (0, 21, 63, 126, 252)
    th, Hv = thin.to_numpy(), Hh.to_numpy()
    frozen = {L: np.zeros_like(Hv) for L in lags}
    i = 0
    while i < len(th):
        if not th[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(th) and th[j + 1]:
            j += 1
        for L in lags:
            if i - 1 - L >= 0:
                frozen[L][i:j + 1] = Hv[i - 1 - L]
        i = j + 1
    p("\n--- attack 2 (placebo): over every thin run hold, unchanged, the book HELD L sessions before the run's "
      "last active decision (L = 0 is that decision's own book; 21 / 63 / 126 / 252 are placebos, declared "
      "before running, none chosen). P&L on thin-decision days only, ann% of the window ---")
    p(f"{'window':<10}{'hold':>8}" + "".join(f"{f'L={L}':>9}" for L in lags))
    for lab, a, b in W:
        n = len(C.loc[a:b])
        m = thin_d.loc[a:b]
        hv = float(C.loc[a:b][m].sum().sum() / n * P)
        cells = []
        for L in lags:
            FL = pd.DataFrame(frozen[L], index=Hh.index, columns=Hh.columns).shift(2).reindex(Rt.index).fillna(0.0)
            cells.append(float((FL * Rt).sum(axis=1).loc[a:b][m].sum() / n * P))
        out.setdefault("placebo", {})[lab] = dict(hold=hv, **{f"L{L}": c for L, c in zip(lags, cells)})
        p(f"{lab:<10}{pct(hv):>8}" + "".join(f"{pct(c):>9}" for c in cells))
    p("how different each placebo book is from L=0: mean cosine similarity over thin decisions "
      "(1 = the same book; a placebo near 1 is not a control)")
    for lab, a, b in W:
        m = thin.loc[a:b].to_numpy()
        pos = np.flatnonzero(Hh.index.isin(thin.loc[a:b].index[m]))
        base = frozen[0][pos]
        sims = []
        for L in lags[1:]:
            other = frozen[L][pos]
            num = (base * other).sum(axis=1)
            den = np.linalg.norm(base, axis=1) * np.linalg.norm(other, axis=1)
            ok = den > 0
            sims.append(float((num[ok] / den[ok]).mean()) if ok.any() else float("nan"))
        out.setdefault("placebo_cos", {})[lab] = dict(zip([f"L{L}" for L in lags[1:]], sims))
        p(f"{lab:<10}" + "".join(f"  L={L}: {c:5.2f}" for L, c in zip(lags[1:], sims)))

    p("\n--- the deferred-flip hold book, same split (ann% thin / active) ---")
    pd_ = res[("hold", "deferred")]["pnl"]
    for lab, a, b in W:
        x, m = pd_.loc[a:b], thin_d.loc[a:b]
        p(f"{lab:<10} thin {pct(x[m].sum() / len(x) * P):>7}  active {pct(x[~m].sum() / len(x) * P):>7}")
        out.setdefault("split_deferred", {})[lab] = dict(thin=float(x[m].sum() / len(x) * P),
                                                         active=float(x[~m].sum() / len(x) * P))
    return out, thin_d


def flatten_gap(H, res, thin, thin_d, dist_end):
    """Flatten minus hold, split by kind of earning day: decided on a thin session
    (flatten earns exactly 0 there), decided on an active session with the two
    held books different (the path after a re-entry from flat), and identical
    held books (difference 0, asserted)."""
    W = [w for w in windows(dist_end) if w[0] not in ("2005-09", "full")]
    out = {}
    p("\n=== flatten minus hold, by kind of earning day (pp/yr of the window) ===")
    p(f"{'window':<10}{'flips':<9}{'total':>8}{'thin dec':>10}{'active, books differ':>22}{'[days]':>8}"
      f"{'identical':>11}")
    for flips in ("instant", "deferred"):
        hf, hh = H[("flatten", flips)], H[("hold", flips)]
        rf, rh = res[("flatten", flips)]["pnl"], res[("hold", flips)]["pnl"]
        # the shifted books' first two rows are NaN (nothing decided yet): a real
        # zero, filled as one. Without the fill NaN != NaN counted 2005-01-03/04
        # as "books differ" (re-derivation, 2026-11-03): FIT [days] read 976 / 979
        # for 974 / 977. P&L was unaffected (both books earn 0 there).
        diffbook = (hf.shift(2).fillna(0.0) != hh.shift(2).fillna(0.0)).any(axis=1).reindex(rf.index)
        if diffbook.isna().any():
            raise AssertionError("the held books do not cover every earning day")
        diffbook = diffbook.astype(bool)
        for lab, a, b in W:
            d = (rf - rh).loc[a:b]
            m, db = thin_d.loc[a:b], diffbook.loc[a:b]
            if not (rf.loc[a:b][m] == 0).all():
                raise AssertionError("the flatten book earned something on a thin-decision day")
            same = ~m & ~db
            if not (d[same] == 0).all():
                raise AssertionError("identical held books earned different P&L")
            n = len(d)
            row = dict(total=float(d.mean() * P), thin=float(d[m].sum() / n * P),
                       differ=float(d[~m & db].sum() / n * P), differ_days=int((~m & db).sum()),
                       same=float(d[same].sum() / n * P))
            out[f"{flips}/{lab}"] = row
            p(f"{lab:<10}{flips:<9}{pct(row['total']):>8}{pct(row['thin']):>10}{pct(row['differ']):>22}"
              f"{row['differ_days']:8d}{pct(row['same']):>11}")
    return out


def runs_table(H, res, thin, a, b, label):
    """Each thin run whose EARNING days fall in [a, b] (a run that began before `a` is
    included, its earning days clipped to the window, so the rows sum to the thin-day split):
    hold's P&L over those earning days, then both books' P&L over the 21 earning days after
    the run (the re-entry; it may overlap the next run), instant flips."""
    rh, rf = res[("hold", "instant")]["pnl"], res[("flatten", "instant")]["pnl"]
    idx = thin.index
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    th = thin.to_numpy()
    runs, i = [], 0
    while i < len(th):
        if not th[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(th) and th[j + 1]:
            j += 1
        runs.append((i, j))
        i = j + 1
    p(f"\n--- thin runs earning in {label}: hold P&L earned on the run's earning days in the window (pp), "
      "then hold / flatten over the next 21 earning days (pp), instant flips ---")
    p(f"{'first':<12}{'last':<12}{'sessions':>9}{'earn days':>10}{'hold on run':>12}{'hold after':>11}{'flat after':>11}")
    rows = []
    for i0, i1 in runs:
        earn = idx[i0 + 2: i1 + 3]                               # decisions i0..i1 earn i0+2..i1+2
        earn = earn[(earn >= a) & (earn <= b)]
        if not len(earn):
            continue
        after = idx[i1 + 3: i1 + 3 + 21]
        on = float(rh.reindex(earn).fillna(0).sum())
        ah, af = float(rh.reindex(after).fillna(0).sum()), float(rf.reindex(after).fillna(0).sum())
        rows.append(dict(first=str(idx[i0].date()), last=str(idx[i1].date()), n=i1 - i0 + 1, earn=len(earn),
                         hold_on=on, hold_after=ah, flat_after=af))
        p(f"{str(idx[i0].date()):<12}{str(idx[i1].date()):<12}{i1 - i0 + 1:9d}{len(earn):10d}{on * 100:12.2f}"
          f"{ah * 100:11.2f}{af * 100:11.2f}")
    p(f"{'sum':<24}{'':9}{sum(r['earn'] for r in rows):10d}{sum(r['hold_on'] for r in rows) * 100:12.2f}"
      f"{sum(r['hold_after'] for r in rows) * 100:11.2f}{sum(r['flat_after'] for r in rows) * 100:11.2f}")
    return rows


RELEASE_TAG = "release-20261102-1"     # the newest release tag on 2026-11-03; carries spec v8 (CEF trial 53)


def _git_show_json(ref_path):
    """A tracked JSON file at a git ref, read with `git show` (read-only). Raises,
    naming the ref, when the clone does not hold it: there is no fallback value."""
    import subprocess
    r = subprocess.run(["git", "-C", str(REPO), "show", ref_path], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git show {ref_path} failed: {r.stderr.strip()}")
    return json.loads(r.stdout)


def w1_rows(H, res, T, thin, keep, Rt):
    """Step 5 context: trial 53's unit book window (W1 2013-06-25..2022-12-30, total return), under both rules.
    The hold row must reproduce the committed impl_core figures; the flatten row is what they would read.

    ADDED 2026-11-03 after review (defect 1): trial 53 is not only approved, it is
    ACTIVE in the newest release tag (commit eca5feb, spec cef_discount.v8.20261101,
    `sizing_multiplier` in the frozen spec there). The m-sized rows read the
    multiplier from that tag's frozen spec (never a literal) and build the book the
    way the spec note says the sleeve does: band in unit weights, `_cap_gross` at
    max_gross_stress / m, emitted as m x the unit weight. The hold row at m is
    asserted equal to trial 53's committed "B sizing_multiplier" row
    (impl_core_2026-11-01_m1.13.json at the tag), so the flatten row beside it is
    the same construction under the live thin rule."""
    a, b = pd.Timestamp("2013-06-25"), pd.Timestamp("2022-12-30")
    p("\n=== STEP 5 context: trial 53's core unit book on its W1 window (2013-06-25..2022-12-30, TR) ===")
    p("(not trial 53's derivation; the same unit book under each thin rule, on the canonical path)")
    out = {}

    def row(label, h, r):
        s = stats(r["pnl"].loc[a:b], r["turn_series"].loc[a:b])
        g = h.abs().sum(axis=1).loc[a:b]
        atcap = float((g >= MAX_GROSS_STRESS - 1e-9).mean())
        s.update(mean_gross=float(g.mean()), at_cap=atcap, sd_daily=float(r["pnl"].loc[a:b].std()))
        out[label] = s
        p(f"{label:<22} SR {s['sr']:.3f} ann {s['ann'] * 100:5.2f}% vol {s['vol'] * 100:5.2f}% "
          f"maxDD {-s['maxdd'] * 100:5.2f}% turn {s['turn']:5.1f}/yr mean gross {s['mean_gross']:.3f} "
          f"at cap {atcap * 100:4.1f}% | BE {s['be']:5.1f}bp | daily sd {s['sd_daily']:.6f}")
        return s

    for key in (("hold", "instant"), ("flatten", "instant"), ("hold", "deferred"), ("flatten", "deferred")):
        row(f"{key[0]}/{key[1]}", H[key], res[key])

    tag_spec = _git_show_json(f"{RELEASE_TAG}:ops/specs/cef_discount.frozen.json")
    if "frozen" not in tag_spec:
        raise AssertionError(f"{RELEASE_TAG}'s spec file has no 'frozen' block")
    m = tag_spec["frozen"].get("sizing_multiplier")
    if not isinstance(m, (int, float)) or not m > 0:
        raise AssertionError(f"{RELEASE_TAG}'s frozen spec has no positive sizing_multiplier ({m!r})")
    if cef_below_min_names(tag_spec["frozen"]) != "flatten":
        raise AssertionError(f"{RELEASE_TAG}'s frozen spec sets below_min_names; the flatten label is wrong there")
    p(f"\n--- trial 53 as ACTIVATED at {RELEASE_TAG} (spec {tag_spec.get('spec_id')}, sizing_multiplier {m}): "
      "m x band_gross_capped(T, band, max_gross_stress / m) ---")
    out["release"] = dict(tag=RELEASE_TAG, spec_id=tag_spec.get("spec_id"), m=float(m))
    for rule in ("hold", "flatten"):
        for flips in ("instant", "deferred"):
            kw = {} if rule == "hold" else dict(below_min_names="flatten", thin=thin)
            h = m * bf.band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS / m,
                                         defer_flips=(flips == "deferred"), **kw)
            row(f"m={m} {rule}/{flips}", h, bf.evaluate(h.loc[keep], Rt))
    ref = _git_show_json(f"{RELEASE_TAG}:results/cef/prereg_voltarget/impl_core_2026-11-01_m1.13.json")
    if float(ref["m"]) != float(m):
        raise AssertionError(f"impl_core's m {ref['m']} is not the tag spec's {m}")
    mine, theirs = out[f"m={m} hold/instant"], ref["TR"]["B sizing_multiplier"]
    for k_mine, k_ref, sign in (("sr", "sr", 1), ("ann", "ann", 1), ("maxdd", "mdd", -1),
                                ("mean_gross", "mean_gross", 1), ("at_cap", "at_cap", 1)):
        if abs(mine[k_mine] - sign * theirs[k_ref]) > 1e-9:
            raise AssertionError(f"m-sized hold book does not reproduce trial 53's {k_ref}: "
                                 f"{mine[k_mine]} vs {sign * theirs[k_ref]}")
    p(f"the m={m} hold/instant row reproduces trial 53's committed 'B sizing_multiplier' row "
      "(SR, ann, maxDD, mean gross, at cap; |diff| <= 1e-9)")
    x = res[("hold", "instant")]["pnl"].loc[a:b]
    eq = (1 + x).cumprod()
    dd = eq / eq.cummax() - 1
    trough = dd.idxmin()
    peak = eq.loc[:trough].idxmax()
    span = x.loc[peak:trough].iloc[1:]
    td = thin.shift(2).reindex(span.index)
    td = td.where(td.notna(), False).astype(bool)
    on_thin = float((1 + span[td]).prod() - 1)
    out["hold_worst_dd"] = dict(peak=str(peak.date()), trough=str(trough.date()), dd=float(dd.min()),
                                days=int(len(span)), thin_days=int(td.sum()), compounded_on_thin=on_thin,
                                compounded_on_active=float((1 + span[~td]).prod() - 1))
    p(f"hold instant worst W1 drawdown {dd.min() * 100:.2f}%: peak {peak.date()} -> trough {trough.date()}, "
      f"{len(span)} earning days of which {int(td.sum())} decided on thin sessions; compounded return on those "
      f"thin days {on_thin * 100:.2f}%, on the active days {out['hold_worst_dd']['compounded_on_active'] * 100:.2f}%")
    p("year-end books (trial 53's W2 proxy holds each of these fixed): held gross under each rule (flatten 0.000 = a thin session)")
    for d in ("2013-12-31", "2014-12-31", "2015-12-31", "2016-12-30", "2017-12-29", "2018-12-31",
              "2019-12-31", "2020-12-31", "2021-12-31", "2022-12-30"):
        ts = pd.Timestamp(d)
        gh = float(H[("hold", "instant")].loc[ts].abs().sum())
        gf = float(H[("flatten", "instant")].loc[ts].abs().sum())
        out.setdefault("year_end", {})[d] = dict(gross_hold=gh, gross_flatten=gf)
        p(f"  {d} gross hold {gh:.3f}  flatten {gf:.3f}")
    return out


def matched(T, Rt, thin, keep, fit_turn):
    """H2 context: the flatten (instant) book at the band width whose FIT turnover equals the hold
    book's, by bisection on turnover only (never on P&L). Nothing is chosen from it."""
    fit = T.index[keep] < HOLDOUT_START

    def turn(bw):
        h = bf.band_gross_capped(T, bw, MAX_GROSS_STRESS, below_min_names="flatten", thin=thin).loc[keep]
        return float(bf.evaluate(h, Rt)["turn_series"][fit].mean() * P), h
    lo, hi = BAND_WIDTH, 0.40
    tlo, thi = turn(lo)[0], turn(hi)[0]
    if not (thi <= fit_turn <= tlo):
        raise ValueError(f"fit turnover {fit_turn:.2f} outside [{thi:.2f} @ {hi}, {tlo:.2f} @ {lo}]")
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        if turn(mid)[0] > fit_turn:
            lo = mid
        else:
            hi = mid
    bw = 0.5 * (lo + hi)
    t_, h = turn(bw)
    r = bf.evaluate(h, Rt)
    p(f"\n=== H2 context: flatten (instant) at band {bw:.4f}, matched on FIT turnover to hold instant "
      f"({fit_turn:.2f}/yr; matched {t_:.2f}) ===")
    out = {"band": bw}
    for lab, a, b in (("FIT <2023", pd.Timestamp(bf.SAMPLE_START), HOLDOUT_START - pd.Timedelta(days=1)),
                      ("H13 2023+", HOLDOUT_START, Rt.index[-1])):
        s = stats(r["pnl"].loc[a:b], r["turn_series"].loc[a:b])
        out[lab] = s
        p(f"{lab:<10} SR {s['sr']:.2f} ann {s['ann'] * 100:.2f}% vol {s['vol'] * 100:.2f}% turn {s['turn']:.1f} "
          "net%/yr " + " / ".join(f"{s['net'][c] * 100:.2f}" for c in COSTS) + f" BE {s['be']:.1f}bp")
    return out


def main():
    live_rule = cef_below_min_names(spec()["frozen"])
    p(f"spec {SPEC_ID}; band {BAND_WIDTH}, max_gross_stress {MAX_GROSS_STRESS}, min_names {MIN_NAMES}, "
      f"min_adv_usd {MIN_ADV_USD:,.0f}; the live sleeve's below_min_names (registry): {live_rule!r}")
    if live_rule != "flatten":
        raise AssertionError("the live rule is no longer 'flatten'; this report's labels are wrong")
    T, R, thin, panel, dist_end, keep, Rt = load()
    p(f"panels: prices to {panel['px'].index.max().date()} (paired with NAV), targets "
      f"{T.index[0].date()}..{T.index[-1].date()}, returns cut at DIST_END {dist_end.date()}")
    H = books(T, thin)
    for defer in (False, True):
        ref = independent_flatten(T, thin, defer)
        got = H[("flatten", "deferred" if defer else "instant")]
        diff = float(np.abs(ref.values - got.values).max())
        if diff > 1e-12:
            raise AssertionError(f"independent flatten loop differs by {diff}")
        p(f"second method 2 [independent loop, flatten {'deferred' if defer else 'instant'}]: max abs diff {diff:.1e}")
    res = {k: bf.evaluate(h.loc[keep], Rt) for k, h in H.items()}
    rep = report(H[("flatten", "instant")].loc[keep], Rt)
    mine = res[("flatten", "instant")]
    for k, a, b in (("fit", None, HOLDOUT_START - pd.Timedelta(days=1)), ("holdout", HOLDOUT_START, None)):
        x = mine["pnl"].loc[a:b]
        if abs(rep[k]["gross_sr"] - x.mean() / x.std() * np.sqrt(P)) > 1e-12:
            raise AssertionError(f"harness.report disagrees on {k}")
    p(f"second method 3 [harness.report, nan_policy='raise', flatten instant]: fit SR {rep['fit']['gross_sr']:.3f} "
      f"ann {rep['fit']['ann_ret'] * 100:.2f}% turn {rep['fit']['turn']:.1f}; holdout SR "
      f"{rep['holdout']['gross_sr']:.3f} ann {rep['holdout']['ann_ret'] * 100:.2f}% turn {rep['holdout']['turn']:.1f}")
    n_thin = {lab: int(thin.loc[a:b].sum()) for lab, a, b in windows(dist_end)}
    p("thin decision dates by window: " + ", ".join(f"{k} {v}" for k, v in n_thin.items()))
    cnt = (panel["z"].reindex(T.index).notna() & (panel["adv"].reindex(T.index) >= MIN_ADV_USD)).sum(axis=1)
    p("eligible names on thin decision dates (count: sessions), by window:")
    for lab, a, b in windows(dist_end):
        c = cnt.loc[a:b][thin.loc[a:b]]
        vc = c.value_counts().sort_index()
        OUT.setdefault("thin_eligible_counts", {})[lab] = {int(k): int(v) for k, v in vc.items()}
        p(f"  {lab:<10} " + ", ".join(f"{int(k)}: {int(v)}" for k, v in vc.items()))
    t23 = thin.loc["2023":]
    if t23.any():
        p(f"2023+ thin dates run {t23[t23].index[0].date()}..{t23[t23].index[-1].date()}; "
          f"since 2026-09-28: {int(thin.loc['2026-09-28':].sum())}")
    OUT["thin_counts"] = n_thin

    rows = table(res, H, Rt, dist_end)
    OUT["step4"], thin_d = step4(H, res, Rt, thin, panel, dist_end, T)
    OUT["gap"] = flatten_gap(H, res, thin, thin_d, dist_end)
    OUT["runs_2020_22"] = runs_table(H, res, thin, "2020-01-01", "2022-12-31", "2020-22")
    OUT["runs_2023"] = runs_table(H, res, thin, "2023-01-01", str(dist_end.date()), "2023+")
    OUT["w1"] = w1_rows(H, res, T, thin, keep, Rt)
    OUT["matched"] = matched(T, Rt, thin, keep, rows[(("hold", "instant"), "FIT <2023")]["turn"])

    (HERE / "run.log").write_text("\n".join(LOG) + "\n")
    (HERE / "results.json").write_text(json.dumps(OUT, indent=1, default=str))


if __name__ == "__main__":
    main()
