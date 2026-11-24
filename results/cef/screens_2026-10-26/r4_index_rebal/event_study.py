"""R4 part 2, step 4: price pressure and reversal around fund-of-CEF index reconstitutions.

WHY: the CRSP-holdings gate passed (crsp_events.py: >= 30 dated, lookahead-free sized
events >= 1 day of ADV on allowed names). This runs the event study declared in NOTE.md
§2.4-2.6 and P2.1 item 7 BEFORE any return was computed. Nothing here was tuned after
looking at an output.

ALIGNMENT. A = announcement close (YYY: after the close on the 6th session before the
effective open [V, current text]; PCEF/XMPT: Monday after the 3rd Friday [U]); E = the last
close at which the index fund trades. shift(2): known at close A, filled at close A+1,
earning from close A+1. W1 = close A+1 -> close E (returns on sessions A+2..E); W2 = close E
-> close E+10 (sessions E+1..E+10). Every return date is asserted <= 2022-12-30 and the
price / NAV / action files are truncated to that date in out/_cache before the house
total-return formula reads them, so no 2023+ value is loaded.

ABNORMAL = total return minus the equal-weight mean of same-family allowed names with no add,
drop or qualifying event in that index at that E and complete returns over the window. An
event with no such control is dropped and counted (no fill). Signed by the flow: +1 add,
-1 drop, sign of the share trade for a reweight. Prediction: signed W1 > 0, signed W2 < 0.
t is clustered by (ETF, E). Controls: (a) each non-changer against the mean of the other
non-changers, with the event's sign, averaged within the event; (b) the event names on
windows shifted 21 sessions earlier against the same control names. Gross only.

Run from SCRATCH/tree: python3 ../r4_index_rebal/event_study.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TREE = HERE.parent / "tree"
sys.path.insert(0, str(TREE))
sys.path.insert(0, str(HERE))
from scripts.cef.spec import UNIVERSE  # noqa: E402
from size_events import FIT_END, WIDE, load_names  # noqa: E402

# numexpr's thread pool spun at ~940% CPU for >10 min on one 7,671 x 17 division inside
# distribution_yield (faulthandler trace, 2026-10-27). numexpr is only an accelerator for the
# same element-wise arithmetic, so it is switched off; results are unchanged by construction.
pd.set_option("compute.use_numexpr", False)

OUT = HERE / "out"
CACHE = OUT / "_cache"
PLACEBO_SHIFT = 21
STUDY_START = pd.Timestamp("2009-01-02")  # first CRSP holdings report 2010-06-30; ADV/placebo need less


def own_split_rulings(R: pd.DataFrame, spl: pd.DataFrame, tl_file: Path) -> Path:
    """A split-rulings file for THIS screen: the team lead's 2026-10-20 rulings (drop_split on a
    split already applied by the vendor) plus, with the same treatment, every further cell the
    house guard itself labels `adjusted` in this frame. NOT a team-lead ruling: the families
    panel carries more such cells over 2009-2022 than C4's pool met, and booking k on them would
    put a phantom -50% to -90% (or x2 to x3) day into a 10-session window. Written to out/."""
    import json
    from scripts.cef.band_frontier import split_factor
    from scripts.cef.data_guards import split_basis_check
    k = split_factor(R.index, R.columns, splits=spl).reindex_like(R)
    hits = split_basis_check(R, k)
    adj = hits[hits.basis == "adjusted"]
    tl = json.loads(Path(tl_file).read_text())
    have = {(x["ticker"], x["ex_date"], x["series"]) for x in tl["splits"]}
    extra = [dict(ticker=r.ticker, ex_date=str(r.ex_date.date()), factor=float(r.factor), series="close",
                  treatment="drop_split",
                  reason=f"R4 screen 2026-10-27: house guard labels this cell `adjusted` (raw ratio {r.raw_ratio:.3f}, "
                         f"booked {r.booked_ratio:.3f}); same defect and treatment as the team lead's 2026-10-20 ruling")
             for r in adj.itertuples() if (r.ticker, str(r.ex_date.date()), "close") not in have]
    doc = {"trial": "none (R4 zero-trial screen)",
           "ruled_by": "R4 screen agent, report-only, mirroring the team lead's 2026-10-20 drop_split ruling; NOT a team-lead ruling",
           "ruled_on": "2026-10-27", "record": "SCRATCH/r4_index_rebal/NOTE.md Part 2",
           "ruling": "drop_split on every cell the guard labels adjusted", "splits": tl["splits"] + extra}
    out = OUT / "r4_split_rulings.json"
    out.write_text(json.dumps(doc, indent=1))
    print(f"split rulings: {len(tl['splits'])} from the team lead's file + {len(extra)} added here (drop_split): "
          + ", ".join(f"{x['ticker']} {x['ex_date']}" for x in extra))
    return out
W2_LEN = 10
ALLOWED = ("deployed13", "wide17", "c4_family")


def truncated_panels(fam: set) -> dict:
    """Write <= FIT_END copies of the price, NAV and action files (scratch only)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    p = pd.read_parquet(TREE / "data/cef/cef_prices.parquet")
    p = p[p.ticker.isin(set(WIDE)) & (p.date <= FIT_END)]
    n = pd.read_parquet(TREE / "data/cef/cef_nav.parquet")
    n = n[n.ticker.isin(set(WIDE)) & (n.date <= FIT_END)]
    d = pd.read_parquet(TREE / "data/cef/cef_distributions.parquet")
    d = d[d.ticker.isin(set(WIDE)) & (d.ex_date <= FIT_END)]
    s = pd.read_parquet(TREE / "data/cef/cef_splits.parquet")
    s = s[s.ticker.isin(set(WIDE)) & (pd.to_datetime(s.ex_date) <= FIT_END)]
    # the live distributions + splits as a yfinance-schema actions file, for total_returns(actions=..)
    act = pd.concat([
        pd.DataFrame({"date": d.ex_date, "ticker": d.ticker, "dividends": d.amount, "stock_splits": 0.0}),
        pd.DataFrame({"date": pd.to_datetime(s.ex_date), "ticker": s.ticker, "dividends": 0.0,
                      "stock_splits": s.stock_split.astype(float)})])
    act = act.groupby(["date", "ticker"], as_index=False).agg(dividends=("dividends", "sum"), stock_splits=("stock_splits", "max"))
    for k, f in (("px17", p), ("nav17", n), ("act17", act)):
        f.to_parquet(CACHE / f"{k}.parquet", index=False)
        out[k] = CACHE / f"{k}.parquet"
    fp = pd.read_parquet(TREE / "data/cef_families/cef_prices.parquet")
    fp = fp[fp.ticker.isin(fam) & (fp.date <= FIT_END)]
    fn = pd.read_parquet(TREE / "data/cef_families/cef_nav.parquet")
    fn = fn[fn.ticker.isin(fam) & (fn.date <= FIT_END)]
    fa = pd.read_parquet(TREE / "data/cef_families/cef_actions.parquet")
    fa = fa[fa.ticker.isin(fam) & (fa.date <= FIT_END)]
    for k, f in (("pxF", fp), ("navF", fn), ("actF", fa)):
        f.to_parquet(CACHE / f"{k}.parquet", index=False)
        out[k] = CACHE / f"{k}.parquet"
    for k in ("px17", "pxF", "nav17", "navF"):
        assert pd.read_parquet(out[k]).date.max() <= FIT_END
    return out


def total_return_panel(paths: dict, fam: set) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(total returns, discount) on every session, allowed names only, <= FIT_END."""
    from scripts.cef.band_frontier import load_families_actions, total_returns
    from scripts.cef.data_guards import guard_closes
    sys.path.insert(0, str(TREE / "scripts/cef"))
    from scripts.cef.c4_families import BAR_RULINGS, SPLIT_RULINGS
    p17 = pd.read_parquet(paths["px17"])
    c17 = p17.pivot_table(index="date", columns="ticker", values="close").sort_index()
    c17 = c17[c17.index >= STUDY_START]
    sess = c17.index
    r17 = total_returns(c17.pct_change(fill_method=None), actions=paths["act17"], prices=paths["px17"])
    pF = pd.read_parquet(paths["pxF"])
    cF = pF.pivot_table(index="date", columns="ticker", values="close").sort_index()
    nvF = pd.read_parquet(paths["navF"]).pivot_table(index="date", columns="ticker", values="nav")
    dist, spl = load_families_actions(paths["actF"])
    cols = sorted(cF.columns)
    # a split and a distribution on one name-date: total_returns refuses to guess the per-share
    # basis, and so does this screen -- the name is excluded from returns (event and control), logged.
    a_ = pd.read_parquet(paths["actF"])
    a_ = a_[(a_.date >= sess[0]) & (a_.date <= sess[-1])]
    clash = sorted(set(a_.loc[(a_.dividends > 0) & (a_.stock_splits != 0), "ticker"]))
    if clash:
        print(f"excluded from returns (split and distribution on one date, basis ambiguous): {clash}")
        cols = [c for c in cols if c not in clash]
    cFg, _ = guard_closes(cF, cols=cols, lo=sess[0], hi=sess[-1], nav=nvF, splits=spl, ex_dates=dist,
                          rulings=BAR_RULINGS, context="r4 event study")
    rpxF = cFg.pct_change(fill_method=None).reindex(index=sess, columns=cols)
    rF = total_returns(rpxF, actions=paths["actF"], prices=paths["pxF"],
                       split_rulings=own_split_rulings(rpxF, spl, SPLIT_RULINGS))
    R = pd.concat([r17, rF], axis=1).reindex(sess)
    nv17 = pd.read_parquet(paths["nav17"]).pivot_table(index="date", columns="ticker", values="nav")
    C = pd.concat([c17, cF], axis=1).reindex(sess)
    N = pd.concat([nv17, nvF], axis=1).reindex(index=sess, columns=C.columns)
    disc = C / N - 1.0
    assert R.index.max() <= FIT_END and disc.index.max() <= FIT_END
    return R, disc


def clustered(x: pd.Series, cl: pd.Series) -> tuple[float, float, int, int]:
    """mean, t clustered by cl (CR1 small-sample factor), N, clusters."""
    x = x.astype(float)
    ok = x.notna()
    x, cl = x[ok], cl[ok]
    n, G = len(x), cl.nunique()
    if n < 2 or G < 2:
        return (float(x.mean()) if n else np.nan), np.nan, n, G
    m = x.mean()
    s = (x - m).groupby(cl).sum()
    se = np.sqrt((s ** 2).sum() * G / (G - 1)) / n
    return float(m), float(m / se) if se > 0 else np.nan, n, G


def main() -> None:
    dep, wide, fam, sealed = load_names()
    Q = pd.read_csv(OUT / "p2_qualifying_shares.csv", parse_dates=["E", "A"])
    EV = pd.read_csv(OUT / "p2_events.csv", parse_dates=["E", "A"])
    if len(Q) < 30:
        raise SystemExit(f"gate not passed ({len(Q)} < 30): the event study does not run")
    if (Q.cls == "SEALED").any() or not Q.cls.isin(ALLOWED).all():
        raise ValueError("a non-allowed name reached the event study")
    paths = truncated_panels(fam)
    R, disc = total_return_panel(paths, fam)
    sess = R.index
    U = pd.read_csv(TREE / "data/cef/cef_universe.csv").set_index("ticker").grp
    F = pd.read_csv(TREE / "data/cef_families/universe.csv").set_index("ticker").family
    famof = {**{t: U[t] for t in WIDE}, **{t: F[t] for t in fam}}
    members = {}
    for f_ in set(famof.values()):
        members[f_] = sorted(t for t, v in famof.items() if v == f_ and t in R.columns)
    # names with an add/drop (any size) or a qualifying event, per (etf, E): never controls
    busy = (pd.concat([EV[EV.kind.isin(["add", "drop"])][["etf", "E", "ticker"]], Q[["etf", "E", "ticker"]]])
            .dropna().groupby(["etf", "E"]).ticker.apply(set).to_dict())

    def win_ret(t, i0, i1):  # compound total return on sessions i0+1..i1 (close i0 -> close i1)
        r = R[t].iloc[i0 + 1:i1 + 1]
        return float(np.prod(1 + r.values) - 1) if len(r) and r.notna().all() else np.nan

    def win_disc(t, i0, i1):
        a, b = disc[t].iloc[i0], disc[t].iloc[i1]
        return float(b - a) if np.isfinite(a) and np.isfinite(b) else np.nan

    rows, dropped = [], []
    for q in Q.itertuples():
        sign = 1.0 if q.kind == "add" else -1.0 if q.kind == "drop" else float(q.sign_sh)
        if not np.isfinite(sign) or sign == 0:
            dropped.append((q.etf, q.E.date(), q.ticker, "no sign"))
            continue
        if q.ticker not in R.columns:
            dropped.append((q.etf, q.E.date(), q.ticker, "no return series"))
            continue
        iA, iE = sess.get_loc(q.A), sess.get_loc(q.E)
        assert iE - iA >= 2, "W1 must have at least one session after the A+1 fill"
        if iE + W2_LEN >= len(sess):
            dropped.append((q.etf, q.E.date(), q.ticker, "W2 runs past the fit window"))
            continue
        assert sess[iE + W2_LEN] <= FIT_END
        ctrl_all = [c for c in members[famof[q.ticker]] if c != q.ticker and c not in busy.get((q.etf, q.E), set())]
        for lab, (a0, a1, b0, b1) in {"event": (iA + 1, iE, iE, iE + W2_LEN),
                                      "placebo": (iA + 1 - PLACEBO_SHIFT, iE - PLACEBO_SHIFT,
                                                  iE - PLACEBO_SHIFT, iE + W2_LEN - PLACEBO_SHIFT)}.items():
            rec = dict(etf=q.etf, E=q.E.date(), ticker=q.ticker, cls=q.cls, kind=q.kind, sign=sign,
                       demand=q.demand_sh, kind_lab=lab, fam=famof[q.ticker])
            for w, (i0, i1) in (("W1", (a0, a1)), ("W2", (b0, b1))):
                ri = win_ret(q.ticker, i0, i1)
                ctrl = [c for c in ctrl_all if np.isfinite(win_ret(c, i0, i1))]
                rc = np.array([win_ret(c, i0, i1) for c in ctrl])
                rec[f"{w}_nctrl"] = len(ctrl)
                rec[f"{w}_ar"] = sign * (ri - rc.mean()) if len(ctrl) and np.isfinite(ri) else np.nan
                di = win_disc(q.ticker, i0, i1)
                dc = np.array([win_disc(c, i0, i1) for c in ctrl])
                dc = dc[np.isfinite(dc)]
                rec[f"{w}_dd"] = sign * (di - dc.mean()) if len(dc) and np.isfinite(di) else np.nan
                if lab == "event":  # control (a): non-changers against the others, event's sign
                    if len(ctrl) >= 2:
                        nc = [sign * (rc[j] - np.delete(rc, j).mean()) for j in range(len(ctrl))]
                        rec[f"{w}_nonchanger"] = float(np.mean(nc))
                    else:
                        rec[f"{w}_nonchanger"] = np.nan
            rows.append(rec)
    X = pd.DataFrame(rows)
    X.to_csv(OUT / "p2_event_study_rows.csv", index=False)
    D = pd.DataFrame(dropped, columns=["etf", "E", "ticker", "why"])
    ev = X[X.kind_lab == "event"].copy()
    pl = X[X.kind_lab == "placebo"].copy()
    ev["cl"] = ev.etf + "|" + ev.E.astype(str)
    pl["cl"] = pl.etf + "|" + pl.E.astype(str)

    def line(lab, s, cl):
        m, t, n, G = clustered(s, cl)
        return f"  {lab:<44} n {n:4d}  clusters {G:3d}  mean {m * 1e4:8.1f}bp  t_cl {t:6.2f}  pos {float((s.dropna() > 0).mean()) * 100 if s.notna().any() else float('nan'):5.1f}%"

    print(f"events in: {len(Q)}; dropped: {len(D)} {D.why.value_counts().to_dict() if len(D) else ''}")
    print(f"no control in family (W1): {int((ev.W1_nctrl == 0).sum())}; median controls {ev.W1_nctrl.median():.0f}")
    print(f"return panel last date read: {R.index.max().date()} (asserted <= {FIT_END.date()})")
    print("\n== SIGNED abnormal total return (prediction: W1 > 0 pressure, W2 < 0 reversal). Gross.")
    for w in ("W1", "W2"):
        print(f"{w}:")
        print(line("treatment", ev[f"{w}_ar"], ev.cl))
        print(line("control (a) same-family non-changers", ev[f"{w}_nonchanger"], ev.cl))
        print(line("control (b) placebo, 21 sessions earlier", pl[f"{w}_ar"], pl.cl))
        print(line("discount change, treatment (signed)", ev[f"{w}_dd"], ev.cl))
        print(line("discount change, placebo", pl[f"{w}_dd"], pl.cl))
    print("\n== by ETF and kind (supplementary; the verdict uses the pooled rows above)")
    for (e, k), g in ev.groupby(["etf", "kind"]):
        print(f" {e} {k}")
        for w in ("W1", "W2"):
            print(line(w, g[f"{w}_ar"], g.cl))
    for e, g in ev.groupby("etf"):
        print(f" {e} all kinds")
        for w in ("W1", "W2"):
            print(line(w, g[f"{w}_ar"], g.cl))
            gp = pl[pl.etf == e]
            print(line(w + " placebo", gp[f"{w}_ar"], gp.cl))
    print(" W1+W2 combined (pressure minus reversal: W1 - W2), treatment and placebo")
    print(line("event W1 - W2", ev.W1_ar - ev.W2_ar, ev.cl))
    print(line("placebo W1 - W2", pl.W1_ar - pl.W2_ar, pl.cl))
    # ---- SUPPLEMENTARY, POST-HOC (added after the pooled result was seen; never used for the verdict)
    print("\n== SUPPLEMENTARY, post-hoc (not used for the verdict)")
    for e, g in ev.groupby("etf"):
        gp = pl[pl.etf == e]
        print(f" {e}: discount change (signed)")
        for w in ("W1", "W2"):
            print(line(w + " treatment", g[f"{w}_dd"], g.cl))
            print(line(w + " placebo", gp[f"{w}_dd"], gp.cl))
    pc = ev[ev.etf == "PCEF"].copy()
    pc["era"] = np.where(pd.to_datetime(pc.E) < pd.Timestamp("2018-01-01"), "2013-17", "2018-22")
    for era, g in pc.groupby("era"):
        print(f" PCEF {era}")
        for w in ("W1", "W2"):
            print(line(w, g[f"{w}_ar"], g.cl))
    g = pc[pc.cls == "deployed13"]
    print(" PCEF, deployed-13 names only")
    for w in ("W1", "W2"):
        print(line(w, g[f"{w}_ar"], g.cl))
    # a late reversal entry: change known only at close E (E+1 fill) or from the next day's
    # holdings file (E+2 fill), when no announcement before E is public (PCEF's A is [U])
    late = []
    for q in Q[Q.etf == "PCEF"].itertuples():
        sign = 1.0 if q.kind == "add" else -1.0 if q.kind == "drop" else float(q.sign_sh)
        iE = sess.get_loc(q.E)
        ctrl_all = [c for c in members[famof[q.ticker]] if c != q.ticker and c not in busy.get((q.etf, q.E), set())]
        rec = dict(cl=q.etf + "|" + str(q.E.date()))
        for lab, i0 in (("W2_fillE1", iE + 1), ("W2_fillE2", iE + 2)):
            ri = win_ret(q.ticker, i0, iE + W2_LEN)
            rc = np.array([x for x in (win_ret(c, i0, iE + W2_LEN) for c in ctrl_all) if np.isfinite(x)])
            rec[lab] = sign * (ri - rc.mean()) if len(rc) and np.isfinite(ri) else np.nan
        late.append(rec)
    L = pd.DataFrame(late)
    print(" PCEF reversal with a late entry (close E+1 / E+2 -> close E+10)")
    print(line("fill E+1", L.W2_fillE1, L.cl))
    print(line("fill E+2", L.W2_fillE2, L.cl))

    # verdict per NOTE.md §2.6
    res = {}
    for w in ("W1", "W2"):
        res[w] = dict(tr=clustered(ev[f"{w}_ar"], ev.cl), nc=clustered(ev[f"{w}_nonchanger"], ev.cl),
                      pb=clustered(pl[f"{w}_ar"], pl.cl))
    hit = [w for w in ("W1", "W2") if np.isfinite(res[w]["tr"][1]) and abs(res[w]["tr"][1]) >= 2
           and ((w == "W1" and res[w]["tr"][0] > 0) or (w == "W2" and res[w]["tr"][0] < 0))]
    ctrl_ok = {w: all(abs(res[w][c][1]) < 1 for c in ("nc", "pb") if np.isfinite(res[w][c][1])) for w in ("W1", "W2")}
    art = [w for w in ("W1", "W2") if any(abs(res[w][c][0]) >= abs(res[w]["tr"][0]) and abs(res[w][c][1]) >= 1
                                          for c in ("nc", "pb"))]
    if hit and all(ctrl_ok[w] for w in hit):
        v = "PROMISING"
    elif art:
        v = "ARTIFACT"
    else:
        v = "NOTHING"
    print(f"\nVERDICT (rule §2.6): {v}; predicted-sign |t|>=2 windows: {hit}; controls |t|<1: {ctrl_ok}; "
          f"control as large as treatment: {art}")


if __name__ == "__main__":
    main()
