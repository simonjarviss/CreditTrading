#!/usr/bin/env python3
"""R3 POST-HOC checks (added after the declared run of exdate_screen.py; report-only; they cannot
change the declared verdict). Fit window only (<= 2022-12-30), same gate, same cells.

    python3 r3_c4_exdate/exdate_posthoc.py        # from SCRATCH; ~30 s; writes out/exdate_posthoc_output.txt

WHY THESE WERE ADDED. The declared run found day 2 of the window carrying most of its total-return
P&L, and a pooled price slope of +0.074 at s+2. One mechanical route the declared tests do not cover:
CRSP books the distribution on s but, for some events, the PRICE drop lands later. Then the total
return is +y on s and -y on s+2, and a short opened by the decision of s (filled s+1) collects the
drop on day 2 without paying the distribution on day 0. P1 classifies where the CRSP PRICE drop
lands, by the same likelihood rule as the NAV test, and asks how much window and day-2 P&L sits on
late-drop events. P2-P6 are descriptive robustness rows: by day and side, by era (H5), by
distribution size, without the largest events, and the CRSP-vs-yfinance amount flags.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exdate_screen as xs                      # noqa: E402  (chdir to the tree happens on import)

LOG: list[str] = []


def say(s=""):
    print(s, flush=True)
    LOG.append(s)


def main() -> int:
    ctx = xs.setup()
    xs.LOG.clear()
    for k in ("Ct", "Cx", "g", "W"):
        xs.assert_fit(ctx[k])
    Ct, Cx, Cd, g, W, held, sl, cols = (ctx[k] for k in ("Ct", "Cx", "Cd", "g", "W", "held", "sl", "cols"))
    idx = ctx["idx"]
    off, own = xs.owner_offsets(ctx["H"].index, cols, ctx["pos"])
    off, own = off.loc[sl], own.loc[sl]
    ev = xs.event_alignment(ctx["crsp"], ctx["qr"], ctx["pool"], ctx["UF"], ctx["fam"], ctx["px"], ctx["nav"],
                            idx, held.loc[sl], W, own, sl)
    xs.LOG.clear()
    E, uP, near = ev["events"], ev["uP"], ev["near"]
    E = xs.dispute_flags(E, idx, ctx["px"], sl)
    say("R3 POST-HOC (added after the declared run; report-only; cannot change the declared verdict). "
        f"Fit window only, <= {xs.FIT_END.date()}. Gate passed in setup().")
    inT = Ct.where(W, 0).to_numpy().sum()
    inX = Cx.where(W, 0).to_numpy().sum()
    D2 = (off == 2) & W
    d2T = Ct.where(D2, 0).to_numpy().sum()

    # ---------------- P1: where the CRSP PRICE drop lands
    n = len(idx)
    rows = []
    for i, (t, s, y) in enumerate(zip(E["ticker"], E["s"], E["y"])):
        u = [uP[t].iat[s + k] if 0 <= s + k < n else np.nan for k in (-1, 0, 1, 2)]
        a = max(0, s - xs.SIG_LOOKBACK - 1)
        h = uP[t].iloc[a:s - 1]
        ok = ~near[t].iloc[a:s - 1] & h.notna()
        hv = h[ok]
        sig = float(hv.std()) if len(hv) >= xs.SIG_MIN else np.nan
        rows.append((u, sig, -y))
    U4 = np.array([r[0] for r in rows], dtype=float)
    sig = np.array([r[1] for r in rows], dtype=float)
    q = np.array([r[2] for r in rows], dtype=float)
    meas = np.isfinite(U4).all(axis=1) & np.isfinite(sig) & (sig > 0) & np.isfinite(q)
    cls = np.array(["unmeasurable"] * len(E), dtype=object)
    Um, qm, s2 = U4[meas], q[meas][:, None], 2 * sig[meas][:, None] ** 2
    base = (Um ** 2).sum(axis=1)[:, None]
    LL = np.hstack([-(base - Um ** 2 + (Um - qm) ** 2) / s2, -base / s2])
    labs = np.array(["-1", "0", "+1", "+2", "none"])
    o = np.argsort(-LL, axis=1)
    best, second = LL[np.arange(len(LL)), o[:, 0]], LL[np.arange(len(LL)), o[:, 1]]
    cls[meas] = np.where(best - second >= xs.LR_MIN, labs[o[:, 0]], "ambiguous")
    E["pcls"] = cls
    say("\nP1. WHERE THE CRSP PRICE DROP LANDS (same likelihood rule as the NAV test; offsets -1, 0, +1, +2, none)")
    say(f"  counts, all {len(E):,}: {E['pcls'].value_counts().to_dict()}")
    say(f"  counts, held {int(E['held'].sum()):,}: {E.loc[E['held'], 'pcls'].value_counts().to_dict()}")
    say(f"  median |y|/sigma_price on measurable events: {np.median(np.abs(q[meas]) / sig[meas]):.2f}")
    p1 = {}
    for c in ("0", "+1", "+2", "-1", "none", "ambiguous", "unmeasurable"):
        M = xs._event_mask(E[E["pcls"] == c], own, W, cols)
        p1[c] = dict(events=int((E["pcls"] == c).sum()), share_window_total=float(Ct.where(M, 0).to_numpy().sum() / inT),
                     share_window_price=float(Cx.where(M, 0).to_numpy().sum() / inX),
                     share_day2_total=float(Ct.where(M & D2, 0).to_numpy().sum() / d2T),
                     share_window_gross=float(g.where(M, 0).to_numpy().sum() / g.where(W, 0).to_numpy().sum()))
        v = p1[c]
        say(f"  price class {c:<13} events {v['events']:5d}: window total share {v['share_window_total']:6.1%}, price-only "
            f"{v['share_window_price']:6.1%}, day-2 total share {v['share_day2_total']:6.1%}, window gross {v['share_window_gross']:6.1%}")
    late = E["pcls"].isin(["+1", "+2"])
    Ml = xs._event_mask(E[late], own, W, cols)
    say(f"  late price drop (+1 or +2): window total share {Ct.where(Ml, 0).to_numpy().sum() / inT:.1%}, "
        f"day-2 total share {Ct.where(Ml & D2, 0).to_numpy().sum() / d2T:.1%}")
    # pooled price slope excluding late-drop events
    sub = E[~late & (E["pcls"] != "unmeasurable")].copy()
    for k, col in zip((1, 2), ("p_p1", "p_p2")):
        d = sub[[col, "y"]].dropna()
        x = -d["y"].to_numpy()
        b = float((x * d[col].to_numpy()).sum() / (x * x).sum())
        say(f"  pooled price slope at s{k:+d} excluding late-drop events: {b:+.3f} (n {len(d)})")

    # ---------------- P2: day x side
    say("\nP2. IN-WINDOW P&L BY DAY AND HELD SIDE (% of capital, summed over the fit; total / price-only / gross share of all held)")
    gs = g.to_numpy().sum()
    for k in (0, 1, 2):
        for side, Ms in (("long", held.loc[sl] > 0), ("short", held.loc[sl] < 0)):
            M = (off == k) & W & Ms
            say(f"  day {k} {side:<5}: total {Ct.where(M, 0).to_numpy().sum() * 100:+8.2f}%  price-only "
                f"{Cx.where(M, 0).to_numpy().sum() * 100:+8.2f}%  gross {g.where(M, 0).to_numpy().sum() / gs:6.2%}")

    # ---------------- P3: eras
    say("\nP3. BY ERA (H5): window and pooled placebo, total basis | price-only CR")
    eras = [("2005-09", "2005-01-01", "2009-12-31"), ("2010-14", "2010-01-01", "2014-12-31"),
            ("2015-19", "2015-01-01", "2019-12-31"), ("2020-22", "2020-01-01", "2022-12-30")]
    for lab, a, b in eras:
        r = xs.wstats(Ct.loc[a:b], g.loc[a:b], W.loc[a:b])
        pl = xs.wstats(Ct.loc[a:b], g.loc[a:b], ctx["Wpm"].loc[a:b])
        rx = xs.wstats(Cx.loc[a:b], g.loc[a:b], W.loc[a:b])
        say(f"  {lab}: S {r['S']:6.1%} G {r['G']:5.1%} CR {r['CR']:5.2f} excess t {r['excess_nw_t']:+.2f} | placebo CR "
            f"{pl['CR']:5.2f} | price-only CR {rx['CR']:5.2f} | all P&L {r['pnl_all_pct']:+.2f}%")

    # ---------------- P4: distribution size
    say("\nP4. BY DISTRIBUTION SIZE (CRSP y = ret - retx on the ex-date)")
    for lab, m in (("y > 2% (specials)", E["y"] > 0.02), ("y <= 2%", E["y"] <= 0.02)):
        M = xs._event_mask(E[m], own, W, cols)
        say(f"  {lab:<18} events {int(m.sum()):5d}: window total share {Ct.where(M, 0).to_numpy().sum() / inT:6.1%}, "
            f"price-only {Cx.where(M, 0).to_numpy().sum() / inX:6.1%}, gross {g.where(M, 0).to_numpy().sum() / g.where(W, 0).to_numpy().sum():6.1%}")

    # ---------------- P5: without the largest events
    say("\nP5. WITHOUT THE LARGEST EVENTS (by |total-return window P&L|)")
    ownW = own.where(W, -1)
    ep = {}
    for t in cols:
        o_ = ownW[t].to_numpy()
        m = o_ >= 0
        if m.any():
            for s, v in pd.Series(Ct[t].to_numpy()[m]).groupby(o_[m]).sum().items():
                ep[(t, int(s))] = float(v)
    eps = pd.Series(ep)
    say(f"  events with window P&L: {len(eps):,}; largest |P&L| event {eps.abs().max() * 100:.2f}% of capital")
    for kdrop in (10, 20, 50):
        top = eps.abs().sort_values(ascending=False).index[:kdrop]
        Etop = pd.DataFrame(list(top), columns=["ticker", "s"])
        Mt = xs._event_mask(Etop, own, W, cols)
        Wk = W & ~Mt
        C2, g2 = Ct.where(~Mt, 0.0), g.where(~Mt, 0.0)       # drop those fund-days from the book entirely
        r = xs.wstats(C2, g2, Wk)
        pl = xs.wstats(C2, g2, ctx["Wpm"] & ~Mt)
        say(f"  without the top {kdrop:>2}: S {r['S']:6.1%} G {r['G']:5.1%} CR {r['CR']:5.2f} excess t {r['excess_nw_t']:+.2f} "
            f"| placebo CR {pl['CR']:5.2f}")

    # ---------------- P6: the CRSP-vs-yfinance amount flags
    say("\nP6. FLAG (a): CRSP vs yfinance amount, the shape of the 788")
    act = pd.read_parquet(xs.TREE / "data/cef_families/cef_actions.parquet", filters=[("date", "<=", xs.FIT_END)])
    act["date"] = pd.to_datetime(act["date"])
    dv = act[act["dividends"] > 0].groupby(["ticker", "date"])["dividends"].sum()
    clp = ctx["px"].pivot_table(index="date", columns="ticker", values="close").reindex(index=idx)
    ratio = []
    for t, s, y, f in zip(E["ticker"], E["s"], E["y"], E["flag_a_amount"]):
        if not f:
            continue
        D = dv.get((t, idx[s]), np.nan)
        cp = clp[t].iat[s - 1]
        ratio.append(D / cp / y if np.isfinite(D) and y > 0 else np.nan)
    r = pd.Series(ratio)
    say(f"  flagged {len(r)}; yfinance/CRSP yield ratio quantiles (5/25/50/75/95%): "
        f"{', '.join(f'{v:.3f}' for v in r.quantile([.05, .25, .5, .75, .95]))}; no yfinance row {int(r.isna().sum())}")
    say(f"  ratio within 2% of 1: {int(((r - 1).abs() <= 0.02).sum())}; below 0.9: {int((r < 0.9).sum())}; above 1.1: {int((r > 1.1).sum())}")
    by_t = E[E["flag_a_amount"]].groupby("ticker").size().sort_values(ascending=False)
    say(f"  flagged events by fund (top 8): {by_t.head(8).to_dict()}")

    # ---------------- P7: the distribution transfer paper drops, by era
    say("\nP7. WHAT PAPER DROPS: distribution leg (total - price-only) by era, %/yr; price-only minus total Sharpe")
    for lab, a, b in eras:
        dl = Cd.loc[a:b].sum(axis=1)
        pt, pp = Ct.loc[a:b].sum(axis=1), Cx.loc[a:b].sum(axis=1)
        say(f"  {lab}: distribution leg {dl.mean() * 252 * 100:+.2f}%/yr; gross SR total {xs.c4.sr_of(pt):.3f}, "
            f"price-only {xs.c4.sr_of(pp):.3f}")

    (xs.OUT / "exdate_posthoc_output.txt").write_text("\n".join(LOG) + "\n")
    say(f"\nwrote {xs.OUT / 'exdate_posthoc_output.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
