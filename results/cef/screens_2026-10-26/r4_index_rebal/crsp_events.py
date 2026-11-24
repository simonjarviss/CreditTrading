"""R4 part 2, steps 1-3: dated index-reconstitution events from CRSP MF holdings, sized, gated.

WHY: part 1 found the flows large enough (full positions ~2 days of ADV) but could date only
15 of ~116 rebalances from archived issuer pages. The team lead staged CRSP's monthly ETF
holdings for YYY, PCEF and XMPT (gitignored cache, licensed). This rebuilds the constituent
changes from report-date snapshots under the rules declared in NOTE.md P2.1, which were
written before any return was computed.

Key rules (NOTE.md P2.1): a snapshot is valid if percent_tna sums to 95..105 (PCEF 2010-07
.. 2012-12 sums to 83-92%: CRSP omits 22-27 names the issuer listed, so those are refused);
a holding is keyed by permno; a change is dated only to the scheduled rebalance its
pre/post snapshots bracket (a report dated within 3 days of E is never an endpoint);
vanish-and-return inside one inter-rebalance period is FLICKER, not an event; merger
suspects are excluded from the gate. Demand = TNA (last month-end before A) x |dw| / ADV63
(sessions strictly before A). No return is computed in this file.

Never writes under data/ or into a tracked file. Outputs go to out/p2_*.csv (scratch).
Run from SCRATCH/tree: python3 ../r4_index_rebal/crsp_events.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TREE = HERE.parent / "tree"
sys.path.insert(0, str(TREE))
sys.path.insert(0, str(HERE))
from scripts.cef.spec import UNIVERSE  # noqa: E402
from size_events import (FIT_END, BAR, WIDE, adv_before, load_adv, load_names,  # noqa: E402
                         schedule)

CACHE = Path("/Users/simonjarvis/Downloads/2027/Projects/Quant - PM2027/2027/.claude/worktrees/simon/"
             "results/events/_cache_r7_r2_pull/cefetf")
OUT = HERE / "out"
VALID_LO, VALID_HI = 95.0, 105.0
EDGE = pd.Timedelta(days=3)
ALLOWED = ("deployed13", "wide17", "c4_family")


def load_crsp():
    for f in ("cefetf_holdings.parquet", "cefetf_monthly_tna.parquet", "cefetf_portnomap.parquet"):
        if not (CACHE / f).exists():
            raise FileNotFoundError(f"staged CRSP file missing: {CACHE / f}")
    h = pd.read_parquet(CACHE / "cefetf_holdings.parquet")
    t = pd.read_parquet(CACHE / "cefetf_monthly_tna.parquet")
    h["report_dt"] = pd.to_datetime(h["report_dt"])
    t["caldt"] = pd.to_datetime(t["caldt"])
    assert h["report_dt"].max() <= pd.Timestamp("2022-12-31") and t["caldt"].max() <= pd.Timestamp("2022-12-31")
    return h, t


def permno_classes(h: pd.DataFrame, dep, wide, fam, sealed) -> tuple[dict, pd.DataFrame]:
    """permno -> (our ticker, class). See NOTE.md P2.1 item 2."""
    cls_of = {}
    audit = []
    # the 13: stocknames table in the crosscheck report (closed-end share codes 14/44)
    txt = (TREE / "results/data/cef_crosscheck_crsp_2026-09-28.md").read_text()
    for m in re.finditer(r"^\|\s+(\d+) \| (\w+)\s+\| [\d\- :]+\| [\d\- :]+\|\s+(\d+) \|", txt, flags=re.M):
        perm, tk, shrcd = int(m.group(1)), m.group(2), int(m.group(3))
        if tk in dep and shrcd in (14, 44):
            cls_of[perm] = (tk, "deployed13")
    got = {v[0] for v in cls_of.values()}
    if got != set(UNIVERSE):
        raise ValueError(f"stocknames table did not give a permno for {sorted(set(UNIVERSE) - got)}")
    # C4: current + other permnos
    pm = pd.read_csv(TREE / "data/cef_families/crsp_permno_map.csv")
    for _, r in pm.iterrows():
        if r.ticker not in fam:
            continue
        ps = [r.current_permno] + [float(x) for x in str(r.other_permnos).split(";") if x not in ("", "nan")]
        for p in ps:
            if np.isfinite(p):
                p = int(p)
                if p in cls_of and cls_of[p] != (r.ticker, "c4_family"):
                    raise ValueError(f"permno claimed twice: {p} {cls_of[p]} vs {r.ticker}")
                cls_of[p] = (r.ticker, "c4_family")
    # wide-only and sealed: the permno(s) their CURRENT ticker carries in the pull
    hp = h.dropna(subset=["permno", "ticker"])
    for tk in sorted((wide - dep) | sealed):
        ps = sorted(set(hp.loc[hp.ticker == tk, "permno"].astype(int)))
        c = "wide17" if tk in wide else "SEALED"
        for p in ps:
            if p in cls_of and cls_of[p][0] != tk:
                raise ValueError(f"permno {p} claimed by {cls_of[p]} and {tk}")
            cls_of[p] = (tk, c)
        audit.append((tk, c, len(ps)))
    # self-check: for the 13, the pull's own ticker->permno must agree with stocknames
    for tk in UNIVERSE:
        ps = set(hp.loc[hp.ticker == tk, "permno"].astype(int))
        want = {p for p, v in cls_of.items() if v[0] == tk}
        if ps and not ps <= want:
            raise ValueError(f"{tk}: pull permnos {ps} not in stocknames {want}")
    return cls_of, pd.DataFrame(audit, columns=["ticker", "class", "n_permnos_in_pull"])


def keyed(h: pd.DataFrame) -> pd.DataFrame:
    h = h.copy()
    nav = h.ticker.fillna("").str.fullmatch(r"X[A-Z]{2,4}X")
    if nav.any():
        raise ValueError(f"NAV-symbol tickers in the CRSP pull: {sorted(h.ticker[nav].unique())} (map them first)")
    tp = h.dropna(subset=["permno", "ticker"]).groupby("ticker").permno.unique()
    uniq = {t: int(v[0]) for t, v in tp.items() if len(v) == 1}
    p = h.permno.copy()
    fill = p.isna() & h.ticker.isin(uniq)
    p[fill] = h.ticker[fill].map(uniq)
    h["key"] = np.where(p.notna(), "P" + p.fillna(-1).astype(int).astype(str),
                        np.where(h.ticker.notna(), "T" + h.ticker.fillna(""), "N" + h.security_name))
    h["permno_k"] = p
    h["filled_permno"] = fill
    return h


def main() -> None:
    dep, wide, fam, sealed = load_names()
    allowed = wide | fam
    dv, sessions = load_adv(allowed)
    a = pd.read_parquet(TREE / "data/cef/cef_prices.parquet", columns=["date", "ticker", "close"])
    b = pd.read_parquet(TREE / "data/cef_families/cef_prices.parquet", columns=["date", "ticker", "close"])
    cl = pd.concat([a[a.ticker.isin(set(WIDE))], b[b.ticker.isin(fam)]])
    cl = cl[cl.date <= FIT_END].pivot_table(index="date", columns="ticker", values="close").sort_index()
    assert cl.index.max() <= FIT_END
    sp1 = pd.read_parquet(TREE / "data/cef/cef_splits.parquet")
    sp1 = sp1.rename(columns={"ex_date": "date"})[["date", "ticker"]]
    act = pd.read_parquet(TREE / "data/cef_families/cef_actions.parquet")
    sp2 = act.loc[act.stock_splits != 0, ["date", "ticker"]]
    SPL = pd.concat([sp1, sp2]).assign(date=lambda x: pd.to_datetime(x.date))

    def close_at(t, d):
        """Close on session d (the announcement), known at A. NaN if the name has no close then."""
        if t not in cl.columns:
            return np.nan
        s_ = cl[t]
        s_ = s_[s_.index <= d].dropna()
        return float(s_.iloc[-1]) if len(s_) and (d - s_.index[-1]).days <= 7 else np.nan

    def has_split(t, d0, d1):
        x = SPL[(SPL.ticker == t) & (SPL.date > d0) & (SPL.date <= d1)]
        return len(x) > 0
    h, tna = load_crsp()
    cls_of, audit = permno_classes(h, dep, wide, fam, sealed)
    h = keyed(h)
    h["our_ticker"] = [cls_of.get(int(p), (None, None))[0] if np.isfinite(p) else None for p in h.permno_k]
    h["cls"] = [cls_of.get(int(p), (None, "outside_panels"))[1] if np.isfinite(p) else "outside_panels" for p in h.permno_k]
    # a ticker-only row whose ticker is one of ours but has no permno is NOT silently ours
    snap = h.groupby(["etf_ticker", "report_dt"]).agg(n=("key", "size"), wsum=("percent_tna", "sum")).reset_index()
    snap["valid"] = snap.wsum.between(VALID_LO, VALID_HI)
    snap.to_csv(OUT / "p2_snapshots.csv", index=False)
    sch = pd.concat([schedule(e, sessions, range(2010, 2023)) for e in ("YYY", "PCEF", "XMPT")])
    sch = sch[sch.E <= FIT_END].sort_values(["etf", "E"]).reset_index(drop=True)

    ev, rb = [], []
    for etf, g in sch.groupby("etf"):
        Es = list(g.E)
        vs = snap[(snap.etf_ticker == etf) & snap.valid].report_dt.sort_values()
        H = h[h.etf_ticker == etf]
        T = tna[tna.etf_ticker == etf].sort_values("caldt")
        for i, row in enumerate(g.itertuples()):
            E, A, win = row.E, row.A, row.window_sessions
            Ep = Es[i - 1] if i > 0 else E - pd.Timedelta(days=200)
            En = Es[i + 1] if i + 1 < len(Es) else E + pd.Timedelta(days=200)
            S_pre = vs[(vs > Ep + EDGE) & (vs < E - EDGE)]
            S_post = vs[(vs > E + EDGE) & (vs < En - EDGE)]
            rec = dict(etf=etf, E=E.date(), A=A.date(), window=win, n_pre=len(S_pre), n_post=len(S_post))
            if S_pre.empty or S_post.empty:
                rb.append({**rec, "datable": False})
                continue
            pre, post = S_pre.max(), S_post.min()
            sets_pre = {d: set(H.loc[H.report_dt == d, "key"]) for d in S_pre}
            sets_post = {d: set(H.loc[H.report_dt == d, "key"]) for d in S_post}
            g0 = H[H.report_dt == pre].groupby("key").agg(w=("percent_tna", "sum"), mv=("market_val", "sum"), sh=("nbr_shares", "sum"),
                                                          tk=("ticker", "first"), nm=("security_name", "first"),
                                                          our=("our_ticker", "first"), cls=("cls", "first"))
            g1 = H[H.report_dt == post].groupby("key").agg(w=("percent_tna", "sum"), mv=("market_val", "sum"), sh=("nbr_shares", "sum"),
                                                           tk=("ticker", "first"), nm=("security_name", "first"),
                                                           our=("our_ticker", "first"), cls=("cls", "first"))
            any_pre = set().union(*sets_pre.values())
            any_post = set().union(*sets_post.values())
            adds = [k for k in g1.index if k not in any_pre]
            drops = [k for k in g0.index if k not in any_post]
            flick_add = [k for k in g1.index if k not in g0.index and k in any_pre]
            flick_drop = [k for k in g0.index if k not in g1.index and k in any_post]
            both = [k for k in g0.index if k in g1.index]
            tb = T[T.caldt < A]
            if tb.empty:
                raise ValueError(f"{etf} {E.date()}: no monthly TNA before the announcement {A.date()}")
            tna_usd = float(tb.mtna.iloc[-1]) * 1e6
            tna_dt = tb.caldt.iloc[-1].date()
            dead_drops = g0.loc[[k for k in drops if g0.cls[k] == "outside_panels"]]
            cont = g0.loc[both].sh.where(g0.loc[both].sh > 0)
            ratio = (g1.loc[both].sh / cont).replace([np.inf, -np.inf], np.nan).dropna()
            if len(ratio) < 10:
                raise ValueError(f"{etf} {E.date()}: only {len(ratio)} continuing names to estimate g")
            gfac = float(ratio.median())
            wmax_pre = float(g0.w.max())
            rb.append({**rec, "datable": True, "pre": pre.date(), "post": post.date(), "tna_usd": tna_usd,
                       "tna_dt": tna_dt, "n_add": len(adds), "n_drop": len(drops), "n_both": len(both),
                       "n_flicker": len(flick_add) + len(flick_drop), "g": gfac})
            for kind, keys, src in (("add", adds, g1), ("drop", drops, g0), ("reweight", both, None)):
                for k in keys:
                    r0 = g0.loc[k] if k in g0.index else None
                    r1 = g1.loc[k] if k in g1.index else None
                    rr = r1 if r1 is not None else r0
                    w0 = float(r0.w) if r0 is not None else 0.0
                    w1 = float(r1.w) if r1 is not None else 0.0
                    cls = rr.cls
                    our = rr.our
                    adv = adv_before(dv, our, A) if (cls in ALLOWED and our) else np.nan
                    dem = tna_usd * abs(w1 - w0) / 100 / adv if (np.isfinite(adv) and adv > 0) else np.nan
                    suspect = ""
                    if cls in ALLOWED and kind in ("add", "reweight"):
                        spons = str(rr.nm).split()[0].upper()
                        need = float(r1.mv) if kind == "add" else float(r1.mv) - (float(r0.mv) if r0 is not None else 0.0)
                        same = dead_drops[dead_drops.nm.astype(str).str.split().str[0].str.upper() == spons] if len(dead_drops) else dead_drops
                        tot = float(same.mv.sum()) if len(same) else 0.0
                        if need > 0 and tot >= 0.5 * need and (kind == "add" or (w1 - w0) > 0.5 * max(w0, 1e-9)):
                            suspect = "merger-suspect (sum): " + ";".join(same.nm.astype(str).str[:24])
                        if w1 > 1.25 * wmax_pre:
                            suspect = (suspect + " | " if suspect else "") + f"over-cap: w1 {w1:.2f} > 1.25 x pre max {wmax_pre:.2f}"
                    # lookahead-free size and sign (NOTE.md P2.1a 6b): shares valued at close A
                    pxA = close_at(our, A) if (cls in ALLOWED and our) else np.nan
                    sh0 = float(r0.sh) if r0 is not None else 0.0
                    sh1 = float(r1.sh) if r1 is not None else 0.0
                    if kind == "add":
                        trade_sh = sh1
                    elif kind == "drop":
                        trade_sh = -sh0
                    else:
                        trade_sh = sh1 - gfac * sh0
                    split_between = bool(cls in ALLOWED and our and has_split(our, pre, post))
                    trade_usd = trade_sh * pxA
                    dem_sh = abs(trade_usd) / adv if (np.isfinite(adv) and adv > 0 and np.isfinite(pxA)) else np.nan
                    if kind == "reweight" and split_between:
                        dem_sh = np.nan
                    ev.append(dict(etf=etf, E=E.date(), A=A.date(), window=win, pre=pre.date(), post=post.date(),
                                   kind=kind, key=k, crsp_ticker=rr.tk, name=rr.nm, ticker=our, cls=cls,
                                   w0=w0, w1=w1, tna_usd=tna_usd, adv63=adv, demand=dem, suspect=suspect,
                                   sh0=sh0, sh1=sh1, g=gfac, close_A=pxA, trade_usd=trade_usd, demand_sh=dem_sh,
                                   sign_sh=float(np.sign(trade_usd)) if np.isfinite(trade_usd) else np.nan,
                                   split_between=split_between))
    RB = pd.DataFrame(rb)
    EV = pd.DataFrame(ev)
    RB.to_csv(OUT / "p2_rebalances.csv", index=False)
    EV.to_csv(OUT / "p2_events.csv", index=False)

    pd.set_option("display.width", 230)
    print(f"ADV panel last date read: {dv.index.max().date()}; CRSP report_dt {h.report_dt.min().date()}..{h.report_dt.max().date()}")
    print("\n== identity: wide-only and sealed tickers -> permnos found in the pull")
    print(audit.groupby(["class", "n_permnos_in_pull"]).size().to_string())
    print(f"rows with permno filled from ticker: {int(h.filled_permno.sum())}; rows with no permno after fill: {int(h.permno_k.isna().sum())}")
    print("\n== snapshots: valid / total by ETF and year")
    snap["y"] = snap.report_dt.dt.year
    print(snap.groupby(["etf_ticker", "y"]).valid.agg(["sum", "size"]).unstack(0).fillna(0).astype(int).to_string())
    print("\n== rebalances datable / scheduled (from inception)")
    incep = {"PCEF": "2010-06-30", "XMPT": "2011-07-31", "YYY": "2012-06-30"}
    RB["live"] = [pd.Timestamp(e) >= pd.Timestamp(incep[t]) for t, e in zip(RB.etf, RB.E)]
    L = RB[RB.live]
    print(L.groupby("etf").datable.agg(["sum", "size"]).to_string())
    print("  datable by year:")
    L2 = L.assign(y=pd.to_datetime(L.E).dt.year)
    print(L2.groupby(["y", "etf"]).datable.sum().unstack().fillna(0).astype(int).to_string())
    print(f"  flicker (vanish-and-return, not events): {int(L.n_flicker.fillna(0).sum())}")
    if EV.empty:
        print("no events")
        return
    EV["sized"] = EV.demand.notna()
    EV["ge1"] = EV.demand >= BAR
    print("\n== events by ETF / kind / class: n, sized, >=1 ADV, median demand (days of ADV)")
    print(EV.groupby(["etf", "kind", "cls"]).agg(n=("key", "size"), sized=("sized", "sum"), ge1=("ge1", "sum"),
                                                med=("demand", "median"), mx=("demand", "max")).round(2).to_string())
    sus = EV[(EV.suspect != "") & EV.ge1]
    print(f"\n== merger suspects at >= 1 ADV (excluded from the gate): {len(sus)}")
    if len(sus):
        print(sus[["etf", "E", "kind", "ticker", "w0", "w1", "demand", "suspect"]].round(2).to_string(index=False))
    q = EV[EV.ge1 & EV.cls.isin(ALLOWED) & (EV.suspect == "") & (pd.to_datetime(EV.A) <= FIT_END) & (EV.window >= 1)].copy()
    q["year"] = pd.to_datetime(q.E).dt.year
    print(f"\n== GATE (CRSP only): dated, sized, >= {BAR} ADV, allowed, non-suspect, A <= {FIT_END.date()}, W1 >= 1: "
          f"{len(q)} (needs 30) -> {'PASS' if len(q) >= 30 else 'FAIL'}")
    print(q.groupby(["year", "etf"]).size().unstack().fillna(0).astype(int).to_string())
    print(q.groupby(["etf", "kind", "cls"]).size().to_string())
    q.to_csv(OUT / "p2_qualifying.csv", index=False)
    qs = EV[(EV.demand_sh >= BAR) & EV.cls.isin(ALLOWED) & (EV.suspect == "") & (pd.to_datetime(EV.A) <= FIT_END) & (EV.window >= 1)].copy()
    qs["year"] = pd.to_datetime(qs.E).dt.year
    print(f"\n== GATE, lookahead-free (shares x close A; P2.1a 6b): {len(qs)} (needs 30) -> {'PASS' if len(qs) >= 30 else 'FAIL'}")
    print(qs.groupby(["year", "etf"]).size().unstack().fillna(0).astype(int).to_string())
    print(qs.groupby(["etf", "kind", "cls"]).size().to_string())
    both_ = EV[EV.cls.isin(ALLOWED) & (EV.suspect == "") & EV.demand.notna() & EV.demand_sh.notna()]
    print("  agreement, TNA x dw vs shares (allowed, non-suspect): spearman by kind")
    print(both_.groupby("kind")[["demand", "demand_sh"]].corr(method="spearman").xs("demand_sh", level=1)["demand"].round(3).to_string())
    print(f"  reweights excluded for a split between snapshots: {int((EV.split_between & (EV.kind == 'reweight')).sum())}")
    qs.to_csv(OUT / "p2_qualifying_shares.csv", index=False)
    print(q[["etf", "E", "A", "window", "kind", "ticker", "cls", "w0", "w1", "tna_usd", "adv63", "demand"]]
          .sort_values(["etf", "E"]).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
