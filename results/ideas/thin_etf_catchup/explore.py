"""Explore: does a thin ETF's gap to its factor hedge still close after the desk's fill delay?

    QUANTT_ENV_FILE=<env> python3 results/ideas/thin_etf_catchup/stage.py
    python3 results/ideas/thin_etf_catchup/explore.py

WHY: a thin ETF's close is often a trade from hours before the bell, so its close-to-close
return lags the market and "catches up" the next day. Everybody who has looked at thin funds
has seen that. The desk decides at t's close and fills at t+1's close, so the catch-up day
itself is not ours. The question that is ours: is there any drift LEFT from t+1's close, in
which funds, and is it bigger than the quoted spread? The graveyard has the neighbouring
kill (single-fund premium/discount, RESEARCH_STATE `single-fund-PD`: the ETF leads a stale
NAV), but nothing on ETF price against liquid ETF prices under shift(2).

FIXED BEFORE ANY RETURN WAS READ (2026-11-16). Only counts had been read (funds a year, the
share of rows with zero dollar volume, which factor funds exist from when).
  PANEL     every CRSP ETF (securitytype FUND, subtype ETF), 2000-01-03 to 2025-12-31, dead
            funds included (stage.py). Returns are CRSP's (distributions and delisting in).
  FACTORS   SPY, IWM, QQQ, EFA, EEM, TLT, HYG, GLD, taken from the same panel so dates and
            closes match. QQQ stands in for "a sector fund" and GLD is added for commodity
            funds; a per-fund sector hedge was not built. A factor is used once it has a
            full 250-session history. The factor funds are never traded as names.
  BETAS     every 21 sessions, OLS with an intercept of the fund's daily return on the
            factors over the 250 sessions STRICTLY BEFORE the estimation day (at least 120
            returns), applied to the next 21 sessions. The intercept is not used.
  GAP       g(i,t) = r(i,t) - beta(i)'f(t). SIGNAL S5 = sum of g over t-4..t (all five
            present); S1 = g(i,t).
  CLASS     by rule, from the same 250 sessions: the factor with the highest squared
            correlation names the class (SPY/IWM/QQQ US equity; EFA/EEM international;
            TLT/HYG bond; GLD commodity); "low fit" if that squared correlation is under
            0.05 (munis, short bonds, currencies land here); "geared or inverse" if the
            one-factor beta on it is below 0 or above 1.75. Geared or inverse funds are out
            of every book. This is a returns-based class, not the prospectus.
  ELIGIBLE  at t: signal present, price >= $5, has a class, and the mean dollar volume of
            the 21 sessions to t (zero-volume days count as zero; 15+ rows) in the bucket:
              THIN $25,000 to $1M (THIN-A $25,000-$250,000, THIN-B $250,000-$1M),
              MID $1M-$10M, LARGE $10M-$100M, LIQUID $100M and over (the control).
  BOOK      each day, within the bucket: long the fifth of funds with the most NEGATIVE
            signal (they lagged their hedge), short the fifth with the most positive, equal
            weights, 50% each side, each fund hedged with -weight x beta in the factor
            funds. Flat under 20 eligible funds. Hold h sessions = the mean of the last h
            days' targets. Decided at t, filled at t+1's close, earns from t+2 (shift(2),
            harness.evaluate).
  MAIN      THIN, S5, hold 5. The other five cells of {S1, S5} x {1, 5, 20} are shown, and
            none is picked afterwards.
  SPLITS    stated now: dollar-volume bucket; class (within THIN, flat under 10 funds);
            whether the fund traded on day t (share volume > 0); long leg and short leg
            apart (a thin ETF is rarely easy to borrow, so the long leg is the tradable one).
  CONTROLS  (1) LIQUID: the same rule where closes are real prices; if the idea is about
            stale closes it should show nothing there, and if LIQUID scores as well the
            result is ordinary residual reversal. (2) THIN with the signal 20 sessions old.
  ARTIFACT TESTS, stated now:
            SKIP  the THIN book filled one session later (three sessions after the decision).
            MID   signal and returns both rebuilt on CRSP's closing mid quote: mid return =
                  (1+ret) x q(t)/q(t-1) - 1 with q = mid/price; a quote counts if bid > 0,
                  ask >= bid and the spread is at most 10% of the mid. Where a held fund has
                  no valid quote that day the CRSP return is used and the share is reported.
            HOLD  buy-and-hold, per event: each long (short) fund's hedged return from t+1's
                  close to t+6's close with no rebalancing, the daily mean of those, against
                  the median quoted spread of the same funds. A result smaller than one
                  spread a round trip is not a result.
  EXPECTED  the catch-up is over before our fill. THIN main near zero on the mid; anything
            positive on trade prices to shrink under SKIP and MID (bounce); LIQUID zero.
  NOT DONE  the international-holiday case (needs home-market calendars the panel lacks).
Gross; no cost is modelled. Aggregates only go to results.json beside this file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
PANEL = Path.home() / "quantt_research" / "thin_etf_catchup" / "crsp_etf_all_daily.parquet"
FACTORS = ["SPY", "IWM", "QQQ", "EFA", "EEM", "TLT", "HYG", "GLD"]
GROUP = {"SPY": "US equity", "IWM": "US equity", "QQQ": "US equity", "EFA": "international",
         "EEM": "international", "TLT": "bond", "HYG": "bond", "GLD": "commodity"}
CLASSES = ["US equity", "international", "bond", "commodity", "low fit", "geared or inverse"]
WIN, STEP, MIN_OBS = 250, 21, 120
MIN_PRICE, MIN_NAMES, MIN_NAMES_CLASS = 5.0, 20, 10
BUCKETS = {"THIN": (25e3, 1e6), "THIN-A": (25e3, 250e3), "THIN-B": (250e3, 1e6),
           "MID": (1e6, 1e7), "LARGE": (1e7, 1e8), "LIQUID": (1e8, np.inf)}
MAX_SPREAD = 0.10


def load():
    """The panel as session x fund arrays, and the factor funds' permnos."""
    px = pd.read_parquet(PANEL)
    px["date"] = pd.to_datetime(px["date"])
    if px.duplicated(["date", "permno"]).any():
        raise ValueError("duplicate fund-day rows in the staged panel")
    last = px.sort_values("date").groupby("permno").tail(1)
    fperm = {}
    for f in FACTORS:
        c = last[(last["ticker"] == f) & (last["date"] == px["date"].max())]["permno"].tolist()
        if len(c) != 1:
            raise ValueError(f"factor fund {f}: {len(c)} live permnos carry the ticker")
        fperm[f] = c[0]
    piv = lambda col: px.pivot(index="date", columns="permno", values=col)
    ret = piv("ret")
    prc, dv, vol, bid, ask = (piv(c).reindex_like(ret) for c in ("prc", "dollar_volume", "vol", "bid", "ask"))
    return ret, prc.abs(), dv, vol, bid, ask, fperm


def masked_fit(Y: np.ndarray, X: np.ndarray):
    """OLS of each column of Y (NaN allowed) on X with an intercept, on that column's own
    valid rows. Returns betas (funds x factors) and the count of valid rows."""
    M = np.isfinite(Y)
    Y0 = np.where(M, Y, 0.0)
    Xc = np.column_stack([np.ones(len(X)), X])
    Mf = M.astype(float)
    XtX = np.einsum("tk,tl,ti->ikl", Xc, Xc, Mf)
    Xty = np.einsum("tk,ti->ik", Xc, Y0)
    n = M.sum(axis=0)
    ok = n >= MIN_OBS
    B = np.full((Y.shape[1], Xc.shape[1]), np.nan)
    if ok.any():
        # a fund whose valid rows leave the factors collinear is left without betas, not guessed
        cond = np.linalg.cond(XtX[ok])
        good = np.where(ok)[0][cond < 1e10]
        B[good] = np.linalg.solve(XtX[good], Xty[good][..., None])[..., 0]
    return B[:, 1:], n


def masked_corr_beta(Y: np.ndarray, x: np.ndarray):
    """Each column's correlation with and one-factor beta on x, over its own valid rows."""
    M = np.isfinite(Y)
    n = M.sum(axis=0).astype(float)
    n[n < MIN_OBS] = np.nan
    Y0 = np.where(M, Y, 0.0)
    mx = (M * x[:, None]).sum(axis=0) / n
    my = Y0.sum(axis=0) / n
    dx = (x[:, None] - mx) * M
    dy = (Y0 - my) * M
    sxy, sxx, syy = (dx * dy).sum(axis=0), (dx * dx).sum(axis=0), (dy * dy).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return sxy / np.sqrt(sxx * syy), sxy / sxx


def betas_and_class(R: np.ndarray, F: np.ndarray):
    """Per session and fund: the betas in force (estimated on data strictly before the
    block's first session) and the class code. Lookahead is asserted: the last row any
    estimate reads is strictly before the first row it is applied to."""
    T, N = R.shape
    K = F.shape[1]
    B = np.full((T, N, K), np.nan, dtype=np.float32)
    cls = np.full((T, N), -1, dtype=np.int8)
    for e in range(WIN, T, STEP):
        lo, hi = e - WIN, e                         # rows lo..hi-1 are read
        assert hi - 1 < e, "betas must be estimated strictly before they are applied"
        use = np.isfinite(F[lo:hi]).all(axis=0)
        if not use[0]:
            raise ValueError("SPY has a missing return inside an estimation window")
        Y = R[lo:hi]
        b, n = masked_fit(Y, F[lo:hi][:, use])
        full = np.zeros((N, K))
        full[:, use] = b
        full[np.isnan(b).any(axis=1)] = np.nan
        best_r2 = np.full(N, -1.0); best_k = np.full(N, -1); best_b = np.full(N, np.nan)
        for k in np.where(use)[0]:
            c, b1 = masked_corr_beta(Y, F[lo:hi, k])
            r2 = np.where(np.isfinite(c), c * c, -1.0)
            better = r2 > best_r2
            best_r2[better], best_k[better], best_b[better] = r2[better], k, b1[better]
        code = np.full(N, -1, dtype=np.int8)
        have = best_k >= 0
        grp = np.array([CLASSES.index(GROUP[f]) for f in FACTORS])
        code[have] = grp[best_k[have]]
        code[have & (best_r2 < 0.05)] = CLASSES.index("low fit")
        code[have & (best_r2 >= 0.05) & ((best_b < 0) | (best_b > 1.75))] = CLASSES.index("geared or inverse")
        code[np.isnan(full).any(axis=1)] = -1
        B[e:e + STEP] = full.astype(np.float32)
        cls[e:e + STEP] = code
    return B, cls


def roll_sum(A: np.ndarray, k: int) -> np.ndarray:
    """Trailing k-row sum; NaN unless all k rows are present."""
    out = np.full_like(A, np.nan)
    ok = np.isfinite(A)
    c = np.cumsum(np.where(ok, A, 0.0), axis=0)
    cn = np.cumsum(ok, axis=0)
    out[k - 1:] = c[k - 1:] - np.vstack([np.zeros((1, A.shape[1])), c[:-k]])
    n = cn[k - 1:] - np.vstack([np.zeros((1, A.shape[1]), dtype=cn.dtype), cn[:-k]])
    out[k - 1:][n < k] = np.nan
    return out


def targets(S: np.ndarray, elig: np.ndarray, min_names: int, side: str = "both") -> np.ndarray:
    """Daily quintile targets from signal S on the eligible funds: +0.5 spread equally over
    the fifth with the lowest signal, -0.5 over the fifth with the highest."""
    W = np.zeros(S.shape)
    for t in range(S.shape[0]):
        idx = np.where(elig[t])[0]
        if len(idx) < min_names:
            continue
        s = S[t, idx]
        order = np.argsort(s, kind="stable")
        q = len(idx) // 5
        if side in ("both", "long"):
            W[t, idx[order[:q]]] = 0.5 / q
        if side in ("both", "short"):
            W[t, idx[order[-q:]]] = -0.5 / q
    return W


def hold_mean(W: np.ndarray, h: int) -> np.ndarray:
    """The mean of the last h days' targets (h overlapping tranches)."""
    if h == 1:
        return W
    c = np.cumsum(W, axis=0)
    out = c.copy()
    out[h:] = c[h:] - c[:-h]
    return out / h


class Lab:
    """Holds the arrays once so each book is a few lines. Everything a book needs at t is
    built from rows <= t; harness.evaluate applies the two-session lag."""

    def __init__(self):
        ret, prc, dv, vol, bid, ask, fperm = load()
        self.dates, self.perm = ret.index, ret.columns
        self.fcol = [self.perm.get_loc(fperm[f]) for f in FACTORS]
        self.R = ret.to_numpy()
        self.F = self.R[:, self.fcol]
        self.prc, self.vol = prc.to_numpy(), vol.to_numpy()
        self.adv = dv.fillna(0.0).where(ret.notna() | dv.notna()).rolling(21, min_periods=15).mean().to_numpy()
        b, a = bid.to_numpy(), ask.to_numpy()
        mid = (a + b) / 2
        with np.errstate(invalid="ignore", divide="ignore"):
            self.spread = np.where((b > 0) & (a >= b) & ((a - b) / mid <= MAX_SPREAD), (a - b) / mid, np.nan)
            q = np.where(np.isfinite(self.spread), mid / self.prc, np.nan)
            qlag = np.vstack([np.full((1, q.shape[1]), np.nan), q[:-1]])
            self.Rmid = (1 + self.R) * q / qlag - 1
        self.B, self.cls = betas_and_class(self.R, self.F)
        Ff = np.where(np.isfinite(self.F), self.F, 0.0)
        hasb = np.isfinite(self.B).all(axis=2)
        np.nan_to_num(self.B, copy=False, nan=0.0)      # from here B is 0 where a fund has no betas; hasb says which
        pred = np.where(hasb, np.einsum("tnk,tk->tn", self.B, Ff.astype(np.float32)).astype(float), np.nan)
        self.G = self.R - pred
        self.Gmid = self.Rmid - pred
        del pred, bid, ask, dv, prc, vol, ret
        self.isfactor = np.zeros(len(self.perm), dtype=bool)
        self.isfactor[self.fcol] = True
        self.Rfill = np.where(np.isfinite(self.R), self.R, 0.0)
        self.Rmidfill = np.where(np.isfinite(self.Rmid), self.Rmid, self.Rfill)

    def eligible(self, S, bucket, *, classes=None, traded=None):
        lo, hi = BUCKETS[bucket]
        geared = CLASSES.index("geared or inverse")
        with np.errstate(invalid="ignore"):
            e = (np.isfinite(S) & (self.prc >= MIN_PRICE) & (self.cls >= 0) & (self.cls != geared)
                 & (self.adv >= lo) & (self.adv < hi) & ~self.isfactor[None, :])
            if classes is not None:
                e &= np.isin(self.cls, [CLASSES.index(c) for c in classes])
            if traded is not None:
                e &= (self.vol > 0) if traded else ~(self.vol > 0)
        return e

    def book(self, S, elig, h, *, min_names=MIN_NAMES, side="both", mid=False, extra_lag=0):
        """Weights -> harness.evaluate. Returns the P&L from the first active session and
        the descriptive figures every row of the card needs."""
        Wfull = targets(S, elig, min_names, side)
        use = np.where((Wfull != 0).any(axis=0))[0]          # only funds ever selected: keeps the frames small
        if len(use) == 0:
            return None, {"note": "never reaches the minimum number of funds"}
        W = Wfull[:, use]
        hedge = -np.einsum("tn,tnk->tk", W, self.B[:, use, :].astype(float))
        Wh, Hh = hold_mean(W, h), hold_mean(hedge, h)
        cols = [f"p{p}" for p in self.perm[use]] + [f"F_{f}" for f in FACTORS]
        H = pd.DataFrame(np.hstack([Wh, Hh]), index=self.dates, columns=cols)
        Rn = (self.Rmidfill if mid else self.Rfill)[:, use]
        Rm = pd.DataFrame(np.hstack([Rn, np.where(np.isfinite(self.F), self.F, 0.0)]), index=self.dates, columns=cols)
        if extra_lag:
            H = H.shift(extra_lag).fillna(0.0)
        res = harness.evaluate(H, Rm)
        active = np.where(np.abs(Wh).sum(axis=1) > 0)[0]
        if len(active) == 0:
            return None, {"note": "never reaches the minimum number of funds"}
        pnl = res["pnl"].iloc[active[0] + harness.EXEC_LAG + extra_lag:]
        heldW = np.vstack([np.zeros((harness.EXEC_LAG + extra_lag, Wh.shape[1])), Wh[:-(harness.EXEC_LAG + extra_lag)]])
        hm = np.zeros(Wfull.shape, dtype=bool)
        hm[:, use] = heldW != 0
        sel = Wfull != 0
        n_day = sel.sum(axis=1)
        etf_turn = np.abs(np.diff(Wh, axis=0)).sum() * 252 / len(Wh[active[0]:])
        info = {"funds_per_day_mean": float(n_day[n_day > 0].mean()), "days_invested": int((n_day > 0).sum()),
                "turnover_per_year_all_legs": float(np.abs(np.diff(np.hstack([Wh, Hh])[active[0]:], axis=0)).sum() * 252 / len(Wh[active[0]:])),
                "turnover_per_year_etf_legs": float(etf_turn),
                "median_adv_usd_selected": float(np.nanmedian(self.adv[sel])),
                "median_price_selected": float(np.nanmedian(self.prc[sel])),
                "median_spread_selected": float(np.nanmedian(self.spread[sel])),
                "mean_spread_selected": float(np.nanmean(self.spread[sel])),
                "share_selected_with_quote": float(np.isfinite(self.spread[sel]).mean()),
                "share_selected_traded_on_t": float((self.vol[sel] > 0).mean()),
                "held_fund_days": int(hm.sum()),
                "held_fund_days_without_crsp_return": int((hm & ~np.isfinite(self.R)).sum()),
                "held_fund_days_without_mid_return": int((hm & ~np.isfinite(self.Rmid)).sum()) if mid else None}
        return pnl, info


def line(name, pnl, info):
    s = explore.stats(pnl)
    print(f"{name:<46} SR {s['sharpe']:+.2f} (t {s['t']:+.2f})  {s['ann_ret']:+.2%}/{s['ann_vol']:.2%}  "
          f"n {info['funds_per_day_mean']:.0f}  turn {info['turnover_per_year_etf_legs']:.0f}x  "
          f"ADV ${info['median_adv_usd_selected']:,.0f}  spread {info['median_spread_selected'] * 1e4:.0f}bp")


def main() -> int:
    L = Lab()
    S5, S1 = roll_sum(L.G, 5), L.G
    S5m, S1m = roll_sum(L.Gmid, 5), L.Gmid
    out = {"panel_last_date": str(L.dates[-1].date()), "panel_first_date": str(L.dates[0].date()),
           "funds_in_panel": int(len(L.perm)),
           "funds_dead_before_last_month": int((pd.DataFrame(L.R, index=L.dates).notna().iloc[-21:].sum() == 0).sum()),
           "fixed": {"factors": FACTORS, "window": WIN, "step": STEP, "min_obs": MIN_OBS, "min_price": MIN_PRICE,
                     "min_names": MIN_NAMES, "min_names_class": MIN_NAMES_CLASS, "buckets_usd": {k: list(v) for k, v in BUCKETS.items()},
                     "max_spread_for_a_quote": MAX_SPREAD}}
    # counts by class among THIN-eligible fund-days (descriptive)
    eT = L.eligible(S5, "THIN")
    eAll = np.isfinite(S5) & (L.cls >= 0)
    out["thin_eligible_fund_days_by_class"] = {c: int((eT & (L.cls == i)).sum()) for i, c in enumerate(CLASSES)}
    out["all_fund_days_by_class"] = {c: int((eAll & (L.cls == i)).sum()) for i, c in enumerate(CLASSES)}
    out["thin_share_traded_on_t"] = float((L.vol[eT] > 0).mean())
    out["thin_share_with_valid_quote"] = float(np.isfinite(L.spread[eT]).mean())
    print("THIN eligible fund-days by class:", out["thin_eligible_fund_days_by_class"])
    print(f"THIN: traded on t {out['thin_share_traded_on_t']:.1%}, valid quote {out['thin_share_with_valid_quote']:.1%}")

    books, pnls = {}, {}

    def run(name, S, elig, h, **kw):
        pnl, info = L.book(S, elig, h, **kw)
        if pnl is None:
            books[name] = info
            print(f"{name:<46} {info['note']}")
            return
        pnls[name] = pnl
        books[name] = {**info, **explore.summarise(pnl)}
        line(name, pnl, info)

    print("\n== MAIN and its legs (THIN, S5, hold 5)")
    run("MAIN THIN S5 h5", S5, eT, 5)
    run("MAIN long leg, hedged", S5, eT, 5, side="long")
    run("MAIN short leg, hedged", S5, eT, 5, side="short")
    print("\n== the grid (THIN), none picked")
    for sname, S in (("S1", S1), ("S5", S5)):
        for h in (1, 5, 20):
            if (sname, h) != ("S5", 5):
                run(f"THIN {sname} h{h}", S, L.eligible(S, "THIN"), h)
    print("\n== by dollar-volume bucket (S5, hold 5); LIQUID is the control")
    for b in ("THIN-A", "THIN-B", "MID", "LARGE", "LIQUID"):
        run(f"{b} S5 h5", S5, L.eligible(S5, b), 5)
    print("\n== by class within THIN (S5, hold 5, flat under 10 funds)")
    for c in CLASSES[:5]:
        run(f"THIN {c} S5 h5", S5, L.eligible(S5, "THIN", classes=[c]), 5, min_names=MIN_NAMES_CLASS)
    print("\n== by whether the fund traded on day t (THIN, S5, hold 5)")
    run("THIN traded on t", S5, L.eligible(S5, "THIN", traded=True), 5)
    run("THIN no trade on t", S5, L.eligible(S5, "THIN", traded=False), 5)
    print("\n== control: the signal 20 sessions old (THIN, hold 5)")
    S5lag = np.vstack([np.full((20, S5.shape[1]), np.nan), S5[:-20]])
    run("THIN S5 lagged 20", S5lag, L.eligible(S5lag, "THIN"), 5)
    print("\n== artifact tests")
    run("SKIP: MAIN filled one session later", S5, eT, 5, extra_lag=1)
    run("MID: THIN S5 h5 on closing mids", S5m, L.eligible(S5m, "THIN"), 5, mid=True)
    run("MID: long leg", S5m, L.eligible(S5m, "THIN"), 5, mid=True, side="long")
    run("MID: short leg", S5m, L.eligible(S5m, "THIN"), 5, mid=True, side="short")
    run("MID + SKIP", S5m, L.eligible(S5m, "THIN"), 5, mid=True, extra_lag=1)
    run("MID: THIN S1 h1", S1m, L.eligible(S1m, "THIN"), 1, mid=True)
    run("MID: LIQUID S5 h5", S5m, L.eligible(S5m, "LIQUID"), 5, mid=True)

    # HOLD: buy-and-hold per event, t+1 close to t+6 close, no rebalancing
    print("\n== HOLD: buy-and-hold per event (THIN, S5), t+1 close to t+6 close")
    hold = {}
    for label, Rn, S in (("trade prices", L.Rfill, S5), ("closing mids", L.Rmidfill, S5m)):
        el = L.eligible(S, "THIN")
        W = targets(S, el, MIN_NAMES)
        C = np.vstack([np.zeros((1, Rn.shape[1])), np.cumsum(np.log1p(np.clip(Rn, -0.999, None)), axis=0)])
        Ff = np.where(np.isfinite(L.F), L.F, 0.0)
        CF = np.vstack([np.zeros((1, Ff.shape[1])), np.cumsum(np.log1p(Ff), axis=0)])
        T = len(Rn)
        fwd = np.full(Rn.shape, np.nan); fwdF = np.full(Ff.shape, np.nan)
        # row t: product of returns on sessions t+2..t+6 = C[t+7] - C[t+2] in the padded cumsum
        fwd[:T - 6] = np.expm1(C[7:T + 1] - C[2:T - 4])
        fwdF[:T - 6] = np.expm1(CF[7:T + 1] - CF[2:T - 4])
        hedged = fwd - np.einsum("tnk,tk->tn", L.B, np.nan_to_num(fwdF, nan=0.0).astype(np.float32)).astype(float)
        hedged[T - 6:] = np.nan
        rows, series = {}, {}
        for leg, m in (("long", W > 0), ("short", W < 0)):
            x = np.where(m, hedged, np.nan)
            cnt = np.isfinite(x).sum(axis=1)
            daily = pd.Series(np.nansum(x, axis=1)[cnt > 0] / cnt[cnt > 0], index=L.dates[cnt > 0])
            ev = hedged[m & np.isfinite(hedged)]
            non = daily.iloc[::5]
            rows[leg] = {"events": int(len(ev)), "mean_bp": float(ev.mean() * 1e4), "median_bp": float(np.median(ev) * 1e4),
                         "share_positive": float((ev > 0).mean()),
                         "daily_mean_bp": float(daily.mean() * 1e4),
                         "t_non_overlapping_days": float(non.mean() / non.std() * np.sqrt(len(non))),
                         "median_spread_bp": float(np.nanmedian(L.spread[m]) * 1e4),
                         "by_era_daily_mean_bp": {f"{a[:4]}-{min(int(b[:4]), L.dates[-1].year)}": float(daily.loc[a:b].mean() * 1e4) for a, b in explore.ERAS if len(daily.loc[a:b]) >= explore.MIN_ERA_DAYS}}
            series[leg] = daily
            print(f"{label:<13} {leg:<5} events {rows[leg]['events']:,}  mean {rows[leg]['mean_bp']:+.1f}bp  median {rows[leg]['median_bp']:+.1f}bp  "
                  f"daily-mean {rows[leg]['daily_mean_bp']:+.1f}bp (t {rows[leg]['t_non_overlapping_days']:+.2f})  median spread {rows[leg]['median_spread_bp']:.0f}bp")
        ls = (series["long"] - series["short"]).dropna()
        non = ls.iloc[::5]
        rows["long less short"] = {"daily_mean_bp": float(ls.mean() * 1e4), "t_non_overlapping_days": float(non.mean() / non.std() * np.sqrt(len(non))),
                                   "by_era_daily_mean_bp": {f"{a[:4]}-{min(int(b[:4]), L.dates[-1].year)}": float(ls.loc[a:b].mean() * 1e4) for a, b in explore.ERAS if len(ls.loc[a:b]) >= explore.MIN_ERA_DAYS}}
        print(f"{label:<13} long less short: {rows['long less short']['daily_mean_bp']:+.1f}bp per 5 sessions (t {rows['long less short']['t_non_overlapping_days']:+.2f})")
        hold[label] = rows
    out["hold_per_event"] = hold
    out["books"] = books
    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=str))
    pd.DataFrame(pnls).to_parquet(PANEL.parent / "pnl_series.parquet")     # book-level series, outside the repo
    print("\nMAIN table\n" + explore.table(books["MAIN THIN S5 h5"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
