"""After-the-fact checks on the pay-date test. NOTHING HERE IS PRE-SPECIFIED.

    python3 results/ideas/cef_drip_paydate/explore.py       (first: it writes events_used.parquet)
    python3 results/ideas/cef_drip_paydate/checks.py

WHY THIS FILE EXISTS. explore.py ran the rule fixed on 2026-11-16 once (2026-11-18, after the
interruption). Its profile showed the excess sitting in three sessions, P-1, P and P+1, and
handing part back from P+2; its calendar-time discount/premium book showed nothing while its
per-event table showed a gap once ex-date windows were blanked. Every item below was chosen
AFTER reading those numbers, so each is a description of what was found, not a test of it:

  A  the same-day difference, discount funds less premium funds: for each pay session with at
     least 3 funds on each side, mean(discount) - mean(premium) of the buy-and-hold relative
     return; t across pay sessions clustered by month. The calendar book weights days, this
     weights pay dates; they disagreed and this says by how much.
  B  shorter windows on the canonical harness (shift(2), same weights and benchmark as the
     main book): hold P-1..P+1 only (decide P-3); and decide AT the pay date (fill P+1 close,
     earn P+2..P+6) on the short side, the part a book could trade against the giveback.
  C  per-event P-1..P+1 by era, by liquidity (21-session ADV at P-3) and by spread, next to
     the closing spread itself: a three-session gain smaller than the spread is not a result.
  D  dollar volume by event session relative to the fund's own 21-session average at P-3,
     discount against premium: a dated buyer should show as volume, not only as price.
  E  the P-1 question: a plan agent cannot buy before the cash is paid. P-1 is split by
     whether P is the first session of a month (then P-1 is the month's last session, where
     the desk already knows CEFs rise).

Alignment is explore.py's: the benchmark for session s is the equal-weighted return of funds
eligible at s-2. Gross. Licensed rows stay under ~/quantt_research/.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False
spec = importlib.util.spec_from_file_location("drip_explore", HERE / "explore.py")
ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
warnings.filterwarnings("ignore", message="Mean of empty slice")


def main() -> int:
    P = ex.load()
    ret, prc, dv = P["ret"], P["prc"], P["dollar_volume"]
    idx, cols = ret.index, ret.columns
    n, m = ret.shape
    use = pd.read_parquet(ex.STAGE / "events_used.parquet")
    assert (cols[use["j"].to_numpy()] == use["permno"].to_numpy()).all()      # same panel as explore.py wrote it on
    adv = dv.rolling(21, min_periods=10).mean()
    elig = ((prc >= ex.MIN_PRICE) & (adv >= ex.MIN_ADV)).to_numpy()
    Rn = ret.to_numpy(); R = ret.fillna(0.0)
    L = harness.EXEC_LAG
    elig_prev = np.vstack([np.zeros((L, m), bool), elig[:-L]])
    uni = np.nanmean(np.where(elig_prev, Rn, np.nan), axis=1)
    exn = (P["div"].fillna(0.0) > 0).to_numpy()
    near_ex = np.zeros((n, m), bool)
    for k in range(-ex.EX_BLANK, ex.EX_BLANK + 1):
        s = np.zeros((n, m), bool)
        if k >= 0:
            s[k:] = exn[:n - k]
        else:
            s[:k] = exn[-k:]
        near_ex |= s
    uni_clean = np.nanmean(np.where(elig_prev & ~near_ex, Rn, np.nan), axis=1)
    Rclean = np.where(near_ex, np.nan, Rn)
    ip, jj = use["iP"].to_numpy(), use["j"].to_numpy()

    def bh(ks, clean=False) -> np.ndarray:
        """Buy-and-hold fund less benchmark over sessions P+k, k in ks; NaN if a session is missing."""
        f = np.ones(len(use)); b = np.ones(len(use)); bad = np.zeros(len(use), bool)
        r, bench = (Rclean, uni_clean) if clean else (Rn, uni)
        for k in ks:
            ok = ip + k < n
            x = np.where(ok, r[np.minimum(ip + k, n - 1), jj], np.nan)
            if clean:
                keep = np.isfinite(x)
                f *= np.where(keep, 1.0 + x, 1.0); b *= np.where(keep, 1.0 + bench[np.minimum(ip + k, n - 1)], 1.0)
                bad |= ~ok
            else:
                bad |= ~np.isfinite(x)
                f *= 1.0 + np.where(np.isfinite(x), x, 0.0); b *= 1.0 + bench[np.minimum(ip + k, n - 1)]
        return np.where(bad, np.nan, f - b)

    W = {"P-1..P+5 (the rule)": range(-1, 6), "P-1..P+1": range(-1, 2), "P-1": [-1], "P": [0], "P+1": [1],
         "P+2..P+6": range(2, 7), "P+2..P+10": range(2, 11)}
    out: dict = {"note": "nothing in this file is pre-specified; see the docstring"}

    # ---- A: same-pay-session difference, discount less premium --------------------------------
    A = {}
    for grp_col in ("disc_grp", "disc_clear"):
        for wname, ks in W.items():
            for clean in (False, True):
                v = pd.Series(bh(ks, clean))
                d = pd.DataFrame({"v": v, "g": use[grp_col].to_numpy(), "iP": ip, "mon": use["pay_month"].to_numpy()}).dropna()
                piv = d[d["g"] != "none"].groupby(["iP", "g"])["v"].agg(["mean", "size"]).unstack()
                okd = (piv[("size", "discount")] >= 3) & (piv[("size", "premium")] >= 3)
                diff = (piv[("mean", "discount")] - piv[("mean", "premium")])[okd]
                mon = d.groupby("iP")["mon"].first().reindex(diff.index)
                A[f"{grp_col} | {wname} | {'ex-blanked' if clean else 'raw'}"] = ex.cluster_t(diff.to_numpy(), mon.to_numpy()) | {"pay_sessions": int(len(diff))}
    out["A_discount_less_premium_same_pay_session"] = A

    # ---- B: shorter windows on the harness ------------------------------------------------------
    def wm(sub, ks) -> np.ndarray:
        mm = np.zeros((n, m), bool)
        for k in ks:
            t = sub["iP"].to_numpy() + k - L
            ok = (t >= 0) & (t < n)
            mm[t[ok], sub["j"].to_numpy()[ok]] = True
        return mm

    def book(long_, short) -> dict:
        H = ex.ls_book(long_, short, idx, cols)
        r = harness.evaluate(H, R)
        p = r["pnl"].iloc[30:-L]
        s = explore.summarise(p)
        return {"full": s["full"], "early_half": s["early_half"]["sharpe"], "late_half": s["late_half"]["sharpe"],
                "eras": {k: v["sharpe"] for k, v in s["eras"].items()}, "turnover_per_year": float(r["turn"])}

    mid_month = use[~use["month_turn"]]
    B = {"long P-1..P+1, short the market (decide P-3)": book(wm(use, range(-1, 2)), elig),
         "long the market, short P+2..P+6 (decide at P)": book(elig, wm(use, range(2, 7))),
         "long P-1..P+1, short P+2..P+6": book(wm(use, range(-1, 2)), wm(use, range(2, 7))),
         "mid-month pay dates only: long P-1..P+1, short the market": book(wm(mid_month, range(-1, 2)), elig),
         "discount funds only: long P-1..P+1, short the market": book(wm(use[use["disc_grp"] == "discount"], range(-1, 2)), elig)}
    out["B_shorter_windows_harness"] = B

    # ---- C: per-event P-1..P+1 by era, liquidity, spread ---------------------------------------
    v3, v7, vback = bh(range(-1, 2)), bh(range(-1, 6)), bh(range(2, 7))
    v3c = bh(range(-1, 2), clean=True)
    mon = use["pay_month"].to_numpy()

    def blk(mask) -> dict:
        mask = np.asarray(mask)
        return {"P-1..P+1": ex.cluster_t(v3[mask], mon[mask]), "P-1..P+1 ex-blanked": ex.cluster_t(v3c[mask], mon[mask]),
                "P+2..P+6": ex.cluster_t(vback[mask], mon[mask]), "P-1..P+5": ex.cluster_t(v7[mask], mon[mask]),
                "median_spread_bp": float(np.nanmedian(use["spread"].to_numpy()[mask]) * 1e4),
                "median_adv_usd": float(np.nanmedian(use["adv"].to_numpy()[mask]))}

    C = {"all": blk(np.ones(len(use), bool))}
    yr = use["pay_year"].to_numpy()
    for a, b in ((2000, 2001), (2002, 2008), (2009, 2015), (2016, 2019), (2020, 2022), (2023, 2025)):
        C[f"era {a}-{b}"] = blk((yr >= a) & (yr <= b))
    advv = use["adv"].to_numpy()
    for lab, lo, hi in (("ADV $0.5-1M", 5e5, 1e6), ("ADV $1-2M", 1e6, 2e6), ("ADV $2-5M", 2e6, 5e6), ("ADV >= $5M", 5e6, np.inf)):
        C[lab] = blk((advv >= lo) & (advv < hi))
    C["mid month"] = blk(~use["month_turn"].to_numpy()); C["month turn"] = blk(use["month_turn"].to_numpy())
    C["discount"] = blk(use["disc_grp"].to_numpy() == "discount"); C["premium"] = blk(use["disc_grp"].to_numpy() == "premium")
    C["monthly payers"] = blk(use["freq"].to_numpy() == "M"); C["quarterly payers"] = blk(use["freq"].to_numpy() == "Q")
    out["C_per_event_three_sessions"] = C

    # ---- D: volume by event session -------------------------------------------------------------
    dvn = dv.to_numpy()
    base = use["adv"].to_numpy()
    D = {}
    for lab, mask in (("all", np.ones(len(use), bool)), ("discount", use["disc_grp"].to_numpy() == "discount"),
                      ("premium", use["disc_grp"].to_numpy() == "premium"), ("top flow third", use["flow_grp"].to_numpy() == "top"),
                      ("bottom flow third", use["flow_grp"].to_numpy() == "bottom")):
        row = {}
        for k in range(-5, 8):
            ok = mask & (ip + k < n)
            x = dvn[np.minimum(ip + k, n - 1), jj] / base
            row[f"P{k:+d}"] = float(np.nanmedian(x[ok]))
        D[lab] = row
    out["D_median_dollar_volume_over_own_21_session_average_at_P-3"] = D

    # ---- E: P-1 when P opens a month ------------------------------------------------------------
    monS = pd.Series(idx.year * 100 + idx.month, index=idx)
    first_of_month = (monS.groupby(monS).cumcount().to_numpy() == 0)
    last_of_month = (monS.groupby(monS).cumcount(ascending=False).to_numpy() == 0)
    vm1, v0, vp1 = bh([-1]), bh([0]), bh([1])
    E = {}
    for lab, mask in (("P is the first session of a month", first_of_month[ip]), ("P is the last session of a month", last_of_month[ip]),
                      ("any other P", ~first_of_month[ip] & ~last_of_month[ip])):
        E[lab] = {"share_of_events": float(mask.mean()), "P-1": ex.cluster_t(vm1[mask], mon[mask]),
                  "P": ex.cluster_t(v0[mask], mon[mask]), "P+1": ex.cluster_t(vp1[mask], mon[mask])}
    out["E_by_position_in_month"] = E

    (HERE / "checks.json").write_text(json.dumps(out, indent=1))
    g = lambda d: f"{d['mean_bp']:+.1f} (t {d['t_clustered_by_month']:+.1f}, med {d['median_bp']:+.1f}, pos {d['share_positive']:.1%}, n {d['n']})" if "mean_bp" in d else f"n {d['n']}"
    print("A  discount less premium, same pay session")
    for k, d in A.items():
        print("  ", k, g(d), "sessions", d["pay_sessions"])
    print("B  harness books")
    for k, b in B.items():
        s = b["full"]
        print(f"   {k:60s} Sharpe {s['sharpe']:.2f} t {s['t']:.2f} ret {s['ann_ret']:.2%} vol {s['ann_vol']:.2%} halves {b['early_half']:.2f}/{b['late_half']:.2f} "
              f"turn {b['turnover_per_year']:.0f} eras " + " ".join(f"{e}:{x:.2f}" for e, x in b["eras"].items()))
    print("C  per event")
    for k, b in C.items():
        print(f"   {k:18s} 3d {g(b['P-1..P+1'])} | 3d exclean {g(b['P-1..P+1 ex-blanked'])} | P+2..6 {g(b['P+2..P+6'])} | spr {b['median_spread_bp']:.0f}bp adv ${b['median_adv_usd'] / 1e6:.2f}M")
    print("D  volume")
    for k, r in D.items():
        print("  ", f"{k:18s}", " ".join(f"{a}:{b:.2f}" for a, b in r.items()))
    print("E  position in month")
    for k, b in E.items():
        print("  ", k, f"share {b['share_of_events']:.2f}", "P-1", g(b["P-1"]), "| P", g(b["P"]), "| P+1", g(b["P+1"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
