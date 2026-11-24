"""Explore: do closed-end funds fall while a unit investment trust that holds them is wound up, and rebound after?

    QUANTT_ENV_FILE=<env> python3 results/ideas/uit_cef_flows/crawl.py index && ... filings && ... sizes
    QUANTT_ENV_FILE=<env> python3 results/ideas/uit_cef_flows/stage.py
    python3 results/ideas/uit_cef_flows/parse.py
    python3 results/ideas/uit_cef_flows/explore.py

PROVENANCE OF THIS RULE. The first researcher was cut off on 2026-11-16 with crawl.py and
stage.py written, the form index a fifth done, and NO explore.py, no rule and no results.json
on disk. This docstring was written on 2026-11-18 before any return was read (only the
prospectus formats, two form 24F-2NT notices and the counts printed by parse.py were looked
at). It is the pre-specified rule.

FIXED BEFORE LOOKING
  trusts     every trust parsed (parse.py) from the form 487 prospectuses of First Trust
             ("FT <n>") and Guggenheim Defined Portfolios filed 2012-2025 that the crawl kept.
             A holding line is a closed-end fund when its ticker is the ticker of a CRSP
             closed-end fund (crsp_cef_daily) within 10 calendar days of the deposit date. A
             trust is a CLOSED-END TRUST when more than half of its holding lines are. Only
             closed-end trusts make events (the lane's rule); the funds held by every other
             parsed trust are counted and shown as a labelled second set, "all trusts".
  event      (fund, T): T is the last session on or before a closed-end trust's Mandatory
             Termination Date, for each closed-end fund it held at deposit. Events of one fund
             on one T are merged; n_series is the number of trusts. The prospectus says the
             trustee sells "during the period beginning nine business days prior to, and no
             later than" that date. T is printed in a prospectus filed more than a year
             earlier, so it is public long before any decision (asserted: filed < T - 30 days).
  eligible   price >= $2 and 21-session average dollar volume >= $100,000, read 10 sessions
             before T (before the selling window, so the selling cannot make a fund eligible).
  market     the equal-weighted total return of every CRSP closed-end fund that is eligible
             (same two tests, known the session before). CRSP total returns throughout.
  windows    buy-and-hold return of the fund less the market's over sessions
               T-9..T      the selling window (expected NEGATIVE; cannot be traded short here)
               T+1..T+10   and T+1..T+20: the rebound as the lane states it
               T+2..T+11   and T+2..T+21: the same with the desk's entry: decide at T's close,
                           fill at the T+1 close, earn from T+2. THIS is the long-only trade.
             Per-event mean weighted by n_series (primary) and unweighted, median, share
             positive, t clustered by the calendar month of T.
  book       calendar time on scripts/research/harness.evaluate, shift(2): each session the
             long leg holds every eligible event fund in its T+2..T+11 window with weight
             proportional to n_series (summing to 1), against the equal-weighted market (-1
             spread over all eligible funds). Flat on a session with no event fund. Long-only
             (no hedge) is shown beside it.
  control    for each event, the 5 eligible funds NOT held by any trust terminating within 30
             sessions of T that had the highest daily-return correlation with the event fund
             over sessions T-280..T-30 (120 common sessions at least). CRSP has no fund
             category; correlation over a window that ends before the event is the stand-in,
             and it reads nothing after T-30. The same windows and the same book are scored on
             the controls. If the idea is wrong, controls score as well as the event funds.
  placebo    the same funds at T-40 sessions.
  splits named in advance: n_series 1 / 2-3 / 4 or more; dollar volume under and over
             $500,000 a day; where a size exists, terciles of the estimated sale as a share of
             the fund's dollar volume over the nine sessions T-18..T-10.
  size/gate  a trust's size at termination is estimated from its registrant's form 24F-2NT
             notices: all units sold less units redeemed before its final fiscal year (HIGH:
             treats the final year's redemptions as the termination itself) and less all
             redemptions (LOW). Sale in a fund = size x its percentage at deposit / 100 [U:
             weights drift, and a registrant with several trusts is split equally]. GATE: if
             the 90th percentile of the HIGH estimate over the fund's nine-session dollar
             volume is under 5%, stop and report without reading returns.
  expected   T-9..T negative, T+2..T+11 positive and above the controls, both growing with
             n_series and with the sale's share of volume.
  for information only: the deposit leg (T+1..T+21 and T+1..T+63 after the deposit date) and
             the daily profile T-15..T+25.
GUARDS scored in the same run: the share of window days with no volume (stale closes); the
closing bid-ask spread at T; the T+1 return alone (bounce off a sold-down close: the
tradable window starts at T+2, which is the skip day); the windows again with every session
within three of the fund's own ex-date removed (the desk's ex-date cycle); funds that stop
trading are in the panel with their delisting return.
LICENSED ROWS never leave ~/quantt_research/; results.json holds aggregates only.
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

assert pd.get_option("compute.use_numexpr") is False      # scripts/research/explore.py says why
import os  # noqa: E402
# UIT_SHUFFLE=<dir>: a test of the CODE on scrambled termination dates, written to <dir>, never to this
# directory. It was used on 2026-11-18 to debug this script before the one real run.
SHUFFLE = os.environ.get("UIT_SHUFFLE")
HERE = Path(SHUFFLE) if SHUFFLE else Path(__file__).resolve().parent
OUT = Path.home() / "quantt_research" / "uit_cef_flows"
PANEL = Path.home() / "quantt_research" / "crsp_cef_daily.parquet"
MIN_PRICE, MIN_ADV, SELL, GATE = 2.0, 100_000.0, 9, 0.05
WINDOWS = {"T-9..T": (-9, 0), "T+1..T+10": (1, 10), "T+1..T+20": (1, 20), "T+2..T+11": (2, 11), "T+2..T+21": (2, 21), "T+1": (1, 1)}
N_PEERS, PEER_GAP = 5, 30


def cluster_stats(x: np.ndarray, w: np.ndarray, month: np.ndarray) -> dict:
    """Weighted mean of per-event returns with a t-statistic clustered by month of T."""
    ok = np.isfinite(x)
    x, w, month = x[ok], w[ok], month[ok]
    if len(x) < 30:
        return {"n": int(len(x))}
    m = float((w * x).sum() / w.sum())
    s = pd.Series(w * (x - m)).groupby(month).sum()
    se = float(np.sqrt((s ** 2).sum()) / w.sum())
    return {"n": int(len(x)), "clusters": int(len(s)), "mean_bp": m * 1e4, "median_bp": float(np.median(x) * 1e4),
            "share_positive": float((x > 0).mean()), "t_clustered": m / se if se > 0 else None}


def bhar(logf: np.ndarray, logm: np.ndarray, pos: np.ndarray, col: np.ndarray, a: int, b: int, n: int) -> np.ndarray:
    """Buy-and-hold fund return less the market's over sessions pos+a..pos+b. NaN if any day is missing.

    logf is the cumulative sum of log(1+ret) with NaN propagated by a separate count of missing
    days, so a window with a missing return is NaN, never silently shortened."""
    lo, hi = pos + a - 1, pos + b
    ok = (lo >= 0) & (hi < n)
    out = np.full(len(pos), np.nan)
    lo_, hi_, c = lo[ok], hi[ok], col[ok]
    f = np.exp(logf[hi_, c] - logf[lo_, c]) - 1.0
    m = np.exp(logm[hi_] - logm[lo_]) - 1.0
    out[ok] = f - m
    return out


def load_events(tickers: pd.DataFrame, dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Map every holding line to a CRSP closed-end fund at the deposit date; type the trusts."""
    T = pd.read_parquet(OUT / "trusts.parquet")
    Hd = pd.read_parquet(OUT / "holdings.parquet")
    if SHUFFLE:      # code test only: every termination date moved 60 to 200 days EARLY at random, so nothing true is read
        rng = np.random.default_rng(0)
        T["termination"] = T["termination"] - pd.to_timedelta(rng.integers(60, 200, len(T)), unit="D")
    tk = tickers.dropna(subset=["ticker"]).sort_values("date")
    Hd = Hd.merge(T[["trust_id", "deposit"]], on="trust_id").sort_values("deposit")
    m = pd.merge_asof(Hd, tk.rename(columns={"date": "panel_date"}), left_on="deposit", right_on="panel_date", by="ticker",
                      direction="nearest", tolerance=pd.Timedelta(days=10))
    m["is_cef"] = m["permno"].notna()
    share = m.groupby("trust_id")["is_cef"].mean()
    T = T.set_index("trust_id")
    T["cef_share"] = share
    T["n_cef"] = m.groupby("trust_id")["is_cef"].sum()
    T["closed_end_trust"] = T["cef_share"] > 0.5
    T = T.reset_index()
    counts = {"trusts_parsed": int(len(T)), "closed_end_trusts": int(T["closed_end_trust"].sum()),
              "trusts_with_any_cef": int((T["n_cef"] > 0).sum()),
              "by_sponsor_closed_end": T[T["closed_end_trust"]].groupby("sponsor").size().to_dict(),
              "closed_end_trusts_by_deposit_year": {int(k): int(v) for k, v in T[T["closed_end_trust"]].groupby(T["deposit"].dt.year).size().items()},
              "median_term_months": float(((T["termination"] - T["deposit"]).dt.days / 30.44)[T["closed_end_trust"]].median()),
              "median_funds_per_closed_end_trust": float(T.loc[T["closed_end_trust"], "n_cef"].median())}
    return T, m[m["is_cef"]].copy(), counts


def sizes() -> pd.DataFrame | None:
    p = OUT / "sizes.parquet"
    return pd.read_parquet(p) if p.exists() else None


def main() -> int:
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    last = df["date"].max()
    ret = df.pivot(index="date", columns="permno", values="ret")
    prc = df.pivot(index="date", columns="permno", values="prc").abs()
    dv = df.pivot(index="date", columns="permno", values="dollar_volume")
    exd = (df.pivot(index="date", columns="permno", values="div").fillna(0.0) > 0)
    dates, cols = ret.index, ret.columns
    n = len(dates)
    colpos = {p: i for i, p in enumerate(cols)}
    adv = dv.rolling(21, min_periods=10).mean()
    elig_now = (prc >= MIN_PRICE) & (adv >= MIN_ADV)
    # ALIGNMENT: the market on session s uses eligibility read at s-1.
    elig = elig_now.shift(1, fill_value=False)
    mkt = ret.where(elig).mean(axis=1)
    T, lines, counts = load_events(df[["ticker", "permno", "date"]], dates)
    assert (T["filed"] < T["termination"]).all()

    def build(trusts: pd.DataFrame) -> pd.DataFrame:
        ev = lines.merge(trusts[["trust_id", "termination", "filed", "sponsor"]], on="trust_id")
        ev = ev[ev["termination"] <= last]
        ev["pos"] = dates.searchsorted(ev["termination"].values, side="right") - 1      # last session ON OR BEFORE T
        assert (dates[ev["pos"].values] <= ev["termination"].values).all()
        assert ((ev["termination"] - ev["filed"]).dt.days > 30).all(), "a termination date must be public a month ahead"
        g = ev.groupby(["permno", "pos"]).agg(n_series=("trust_id", "nunique"), trusts=("trust_id", lambda s: list(s)),
                                               pct=("pct", "sum")).reset_index()
        g["col"] = g["permno"].map(colpos)
        ref = np.clip(g["pos"].values - 10, 0, n - 1)
        g["eligible"] = elig_now.values[ref, g["col"].values] & (g["pos"].values - 10 >= 0)
        g["adv"] = adv.values[ref, g["col"].values]
        g["price"] = prc.values[ref, g["col"].values]
        g["T"] = dates[g["pos"].values]
        return g, ev

    ce = T[T["closed_end_trust"]]
    E_all, ev_lines = build(ce)
    counts["fund_events_before_eligibility"] = int(len(E_all))
    E = E_all[E_all["eligible"]].reset_index(drop=True)
    counts["fund_events"] = int(len(E))
    counts["fund_events_per_year"] = {int(k): int(v) for k, v in E.groupby(E["T"].dt.year).size().items()}
    counts["distinct_funds"] = int(E["permno"].nunique())
    counts["distinct_termination_sessions"] = int(E["pos"].nunique())
    counts["n_series_distribution"] = {str(k): int(v) for k, v in E["n_series"].clip(upper=6).value_counts().sort_index().items()}
    any_tr, _ = build(T[T["n_cef"] > 0])
    counts["fund_events_all_trusts_eligible"] = int(any_tr["eligible"].sum())

    # ---- the live calendar (added 2026-11-18, second resumption; reads no return) ----------------------------
    # Terminations scheduled in the 12 months after today, from prospectuses already filed. The crawl ends with
    # the 2025 Q4 index, so a trust deposited in 2026 with a term under two years is missing [U: undercount].
    # Fund names here come from public prospectuses; the count is of trusts, not of dollars.
    today = pd.Timestamp("2026-11-18")
    fut = ce[(ce["termination"] > today) & (ce["termination"] <= today + pd.DateOffset(months=12))]
    fl = lines.merge(fut[["trust_id", "termination", "sponsor"]], on="trust_id")
    fl["window"] = fl["termination"].dt.to_period("M").astype(str)
    top = fl.groupby("ticker")["trust_id"].nunique().sort_values(ascending=False)
    same_day = fl.groupby(["ticker", "termination"])["trust_id"].nunique()
    counts["calendar_next_12_months"] = {
        "as_of": str(today.date()), "closed_end_trusts_terminating": int(len(fut)), "by_sponsor": fut.groupby("sponsor").size().to_dict(),
        "termination_dates": int(fut["termination"].nunique()),
        "trusts_by_month": {k: int(v) for k, v in fut.groupby(fut["termination"].dt.to_period("M").astype(str)).size().items()},
        "fund_events": int(len(same_day)), "distinct_funds": int(fl["ticker"].nunique()),
        "max_trusts_on_one_fund_one_date": int(same_day.max()) if len(same_day) else 0,
        "funds_in_most_trusts": {k: int(v) for k, v in top.head(15).items()}}

    # ---- size and the gate (no return read above this line or in this block) -------------------------------
    sz = sizes()
    gate = {"sized": False}
    E["sale_high"] = np.nan; E["sale_low"] = np.nan
    if sz is not None:
        per = ev_lines.merge(sz, on="trust_id", how="left")
        per["sale_high"] = per["size_high"] * per["pct"] / 100.0
        per["sale_low"] = per["size_low"] * per["pct"] / 100.0
        s = per.groupby(["permno", "pos"]).agg(sale_high=("sale_high", lambda v: v.sum(min_count=len(v))),
                                               sale_low=("sale_low", lambda v: v.sum(min_count=len(v)))).reset_index()
        E = E.drop(columns=["sale_high", "sale_low"]).merge(s, on=["permno", "pos"], how="left")
        cdv = dv.fillna(0.0).cumsum().values
        lo, hi = E["pos"].values - 19, E["pos"].values - 10
        ok = lo >= 0
        vol9 = np.full(len(E), np.nan)
        vol9[ok] = cdv[hi[ok], E["col"].values[ok]] - cdv[lo[ok], E["col"].values[ok]]
        E["vol9"] = vol9
        E["share_high"] = E["sale_high"] / E["vol9"]
        E["share_low"] = E["sale_low"] / E["vol9"]
        q = lambda c: {f"p{int(k * 100)}": float(v) for k, v in E[c].dropna().quantile([.1, .25, .5, .75, .9, .95]).items()}
        ce_sz = ce.merge(sz, on="trust_id", how="left")
        gate = {"sized": True, "closed_end_trusts_sized": int(ce_sz["size_high"].notna().sum()), "closed_end_trusts": int(len(ce_sz)),
                "trust_size_high_usd": {f"p{int(k * 100)}": float(v) for k, v in ce_sz["size_high"].dropna().quantile([.1, .25, .5, .75, .9]).items()},
                "trust_size_low_usd": {f"p{int(k * 100)}": float(v) for k, v in ce_sz["size_low"].dropna().quantile([.1, .25, .5, .75, .9]).items()},
                "events_sized": int(E["share_high"].notna().sum()), "sale_usd_high": q("sale_high"),
                "sale_over_nine_session_volume_high": q("share_high"), "sale_over_nine_session_volume_low": q("share_low")}
        gate["passes"] = bool(E["share_high"].quantile(0.9) >= GATE)
    print(json.dumps(counts, indent=1)); print(json.dumps(gate, indent=1))
    if gate.get("sized") and not gate["passes"]:
        (HERE / "results.json").write_text(json.dumps({"panel_last_date": str(last.date()), "counts": counts, "gate": gate,
                                                       "stopped_at_gate": True}, indent=1))
        print("GATE FAILED: stopped before any return"); return 0

    # ---- returns from here ---------------------------------------------------------------------------------
    R = ret.values
    miss = np.isnan(R)
    logf = np.where(miss, 0.0, np.log1p(np.where(miss, 0.0, R))).cumsum(axis=0)
    nmiss = miss.cumsum(axis=0)
    logm = np.log1p(mkt.fillna(0.0).values).cumsum()

    def win(pos, col, a, b):
        x = bhar(logf, logm, pos, col, a, b, n)
        lo, hi = pos + a - 1, pos + b
        ok = (lo >= 0) & (hi < n)
        gap = np.zeros(len(pos), bool)
        gap[ok] = (nmiss[hi[ok], col[ok]] - nmiss[lo[ok], col[ok]]) > 0
        x[gap] = np.nan
        return x

    month = (E["T"].dt.year * 100 + E["T"].dt.month).values
    w = E["n_series"].values.astype(float)
    pos, col = E["pos"].values, E["col"].values
    for k, (a, b) in WINDOWS.items():
        E[k] = win(pos, col, a, b)

    # controls: correlation peers not held by any trust terminating within PEER_GAP sessions
    held_pos = E_all.groupby("col")["pos"].apply(lambda s: np.sort(s.values)).to_dict()
    peers = np.full((len(E), N_PEERS), -1)
    Rz = ret.values
    for p_, idx in E.groupby("pos").indices.items():
        a0, b0 = p_ - 280, p_ - 30
        if a0 < 0:
            continue
        blk = Rz[a0:b0 + 1]
        okc = (~np.isnan(blk)).sum(axis=0) >= 240                      # nearly complete history, so correlations share sessions
        ref = p_ - 10
        pool = okc & elig_now.values[ref]
        for c_, hp in held_pos.items():
            j = np.searchsorted(hp, p_ - PEER_GAP)
            if j < len(hp) and hp[j] <= p_ + PEER_GAP:
                pool[c_] = False
        pool_idx = np.where(pool)[0]
        if len(pool_idx) < N_PEERS:
            continue
        ev_cols = E["col"].values[idx]
        use = np.unique(np.concatenate([pool_idx, ev_cols[okc[ev_cols]]]))
        z = np.nan_to_num(blk[:, use] - np.nanmean(blk[:, use], axis=0))
        z /= np.sqrt((z ** 2).sum(axis=0)) + 1e-12
        loc = {c_: i for i, c_ in enumerate(use)}
        pl = np.array([loc[c_] for c_ in pool_idx])
        for i, c_ in zip(idx, ev_cols):
            if c_ not in loc:
                continue
            cor = z[:, pl].T @ z[:, loc[c_]]
            peers[i] = pool_idx[np.argsort(-cor)[:N_PEERS]]
    has = peers[:, 0] >= 0
    counts["events_with_controls"] = int(has.sum())
    for k, (a, b) in WINDOWS.items():
        c = np.full(len(E), np.nan)
        if has.any():
            c[has] = np.nanmean(np.column_stack([win(pos[has], peers[has, j], a, b) for j in range(N_PEERS)]), axis=1)
        E["ctl " + k] = c
        E["plc " + k] = win(pos - 40, col, a, b)

    def table(sub: pd.DataFrame, weighted=True) -> dict:
        mo = (sub["T"].dt.year * 100 + sub["T"].dt.month).values
        ww = sub["n_series"].values.astype(float) if weighted else np.ones(len(sub))
        out = {}
        for k in WINDOWS:
            out[k] = {"event": cluster_stats(sub[k].values, ww, mo), "control": cluster_stats(sub["ctl " + k].values, ww, mo),
                      "event_less_control": cluster_stats((sub[k] - sub["ctl " + k]).values, ww, mo),
                      "placebo_T-40": cluster_stats(sub["plc " + k].values, ww, mo)}
        return out

    res_ev = {"weighted_by_n_series": table(E), "unweighted": table(E, False)}
    eras = {"2012-2015": ("2012", "2015"), "2016-2019": ("2016", "2019"), "2020-2022": ("2020", "2022"), "2023-2025": ("2023", "2025")}
    res_ev["by_era"] = {k: table(E[(E["T"] >= a) & (E["T"] <= b + "-12-31")]) for k, (a, b) in eras.items()}
    mid = E["T"].sort_values().iloc[len(E) // 2]
    res_ev["halves"] = {"split": str(mid.date()), "early": table(E[E["T"] <= mid]), "late": table(E[E["T"] > mid])}
    res_ev["by_n_series"] = {"1": table(E[E["n_series"] == 1]), "2-3": table(E[E["n_series"].between(2, 3)]), "4+": table(E[E["n_series"] >= 4])}
    res_ev["by_dollar_volume"] = {"under_500k": table(E[E["adv"] < 5e5]), "500k_and_over": table(E[E["adv"] >= 5e5])}
    if gate.get("sized"):
        sh = E["share_high"]
        qs = sh.quantile([1 / 3, 2 / 3]).values
        res_ev["by_sale_share_tercile"] = {"cuts": [float(v) for v in qs], "low": table(E[sh <= qs[0]]),
                                           "mid": table(E[(sh > qs[0]) & (sh <= qs[1])]), "high": table(E[sh > qs[1]])}

    # daily profile, weighted by n_series: fund less market, session by session
    A = (ret.sub(mkt, axis=0)).values
    prof = {}
    for k in range(-15, 26):
        p2 = pos + k
        ok = (p2 >= 0) & (p2 < n)
        v = np.full(len(E), np.nan); v[ok] = A[p2[ok], col[ok]]
        prof[f"T{k:+d}"] = cluster_stats(v, w, month)

    # guards
    liq = {"median_price": float(E["price"].median()), "median_adv_usd": float(E["adv"].median()),
           "p25_adv_usd": float(E["adv"].quantile(.25)), "share_under_500k": float((E["adv"] < 5e5).mean())}
    vol0 = (dv.fillna(0.0) <= 0).values
    zc = vol0.cumsum(axis=0)
    okp = (pos - 10 >= 0) & (pos + 11 < n)
    liq["share_of_window_days_with_no_volume_T-9..T+11"] = float(((zc[pos[okp] + 11, col[okp]] - zc[pos[okp] - 10, col[okp]]) / 21).mean())
    qp = OUT / "cef_quotes.parquet"
    if qp.exists() and qp.stat().st_size > 0:
        qd = pd.read_parquet(qp); qd["date"] = pd.to_datetime(qd["date"])
        qd = qd[(qd["bid"] > 0) & (qd["ask"] >= qd["bid"])]
        qd["spr"] = (qd["ask"] - qd["bid"]) / ((qd["ask"] + qd["bid"]) / 2)
        e2 = E[["permno", "T"]].merge(qd[["permno", "date", "spr"]], left_on=["permno", "T"], right_on=["permno", "date"], how="left")
        liq["closing_spread_bp_at_T"] = {"median": float(e2["spr"].median() * 1e4), "mean": float(e2["spr"].mean() * 1e4),
                                         "p75": float(e2["spr"].quantile(.75) * 1e4), "matched": int(e2["spr"].notna().sum()),
                                         "quotes_last_date": str(qd["date"].max().date())}
    else:
        liq["closing_spread_bp_at_T"] = "UNMEASURED: cef_quotes.parquet not staged"
    # the ex-date cycle: sum of daily fund-less-market returns with sessions within 3 of an own ex-date removed
    near = np.zeros_like(exd.values)
    for k in range(-3, 4):
        near |= exd.shift(k, fill_value=False).values
    A0 = np.where(np.isnan(A), 0.0, A)
    cA, cAx = A0.cumsum(axis=0), np.where(near, 0.0, A0).cumsum(axis=0)
    exg = {}
    for k, (a, b) in WINDOWS.items():
        lo, hi = pos + a - 1, pos + b
        ok = (lo >= 0) & (hi < n)
        full = np.full(len(E), np.nan); cut = full.copy()
        full[ok] = cA[hi[ok], col[ok]] - cA[lo[ok], col[ok]]
        cut[ok] = cAx[hi[ok], col[ok]] - cAx[lo[ok], col[ok]]
        exg[k] = {"sum_of_daily_all_sessions": cluster_stats(full, w, month), "without_sessions_near_own_ex_date": cluster_stats(cut, w, month)}

    # deposit leg, for information
    dep = lines.merge(ce[["trust_id", "deposit"]], on="trust_id", suffixes=("", "_t"))
    dep["pos"] = dates.searchsorted(dep["deposit"].values, side="left")
    dep = dep[dep["pos"] < n - 1]
    dg = dep.groupby(["permno", "pos"]).agg(n_series=("trust_id", "nunique")).reset_index()
    dg["col"] = dg["permno"].map(colpos)
    dg = dg[elig_now.values[np.clip(dg["pos"].values - 1, 0, n - 1), dg["col"].values]]
    dmo = (dates[dg["pos"].values].year * 100 + dates[dg["pos"].values].month).values
    deposit = {k: cluster_stats(win(dg["pos"].values, dg["col"].values, a, b), dg["n_series"].values.astype(float), dmo)
               for k, (a, b) in {"D-10..D-1": (-10, -1), "D+1..D+21": (1, 21), "D+1..D+63": (1, 63)}.items()}

    # ---- calendar-time book on the harness ----------------------------------------------------------------
    def earn_matrix(pos_, col_, w_):
        M = np.zeros((n, len(cols)))
        for p_, c_, w__ in zip(pos_, col_, w_):
            a, b = p_ + 2, min(p_ + 11, n - 1)
            if a < n:
                M[a:b + 1, c_] += w__
        return pd.DataFrame(M, index=dates, columns=cols).where(elig, 0.0)

    def run(earn: pd.DataFrame):
        tot = earn.sum(axis=1)
        long_ = earn.div(tot.where(tot > 0), axis=0).fillna(0.0)
        ne = elig.sum(axis=1)
        short = elig.astype(float).div(ne.where(ne > 0), axis=0).fillna(0.0).mul((tot > 0).astype(float), axis=0)
        Rf = ret.fillna(0.0)
        out = {}
        for nm, W in (("hedged", long_ - short), ("long_only", long_)):
            # ALIGNMENT: W is the exposure EARNED on session s; the harness holds H two sessions later, so the
            # decision for a weight earned at T+2 is dated T. assert below that no weight is earned before T+2.
            r = harness.evaluate(W.shift(-harness.EXEC_LAG).fillna(0.0), Rf)
            out[nm] = (r["pnl"], float(r["turn"]))
        return out, long_

    first_ev = E.groupby("col")["pos"].min()
    earn = earn_matrix(pos, col, w)
    for c_, p0 in first_ev.items():
        assert earn.values[:p0 + 2, c_].sum() == 0.0, "a weight is earned before T+2"
    bk, long_w = run(earn)
    ctl_earn = earn_matrix(np.repeat(pos[has], N_PEERS), peers[has].ravel(), np.repeat(w[has] / N_PEERS, N_PEERS))
    cb, _ = run(ctl_earn)
    start = dates[max(E["pos"].min() - 1, 0)]
    cut = lambda s: s.loc[start:].iloc[:-harness.EXEC_LAG]
    pnl = cut(bk["hedged"][0])
    held_adv = (adv.where(long_w > 0)).loc[start:].stack()
    res = explore.summarise(pnl, controls={"controls, same book": cut(cb["hedged"][0]),
                                           "event less control (long-only legs)": cut(bk["long_only"][0]) - cut(cb["long_only"][0])},
                            extra={"panel_last_date": str(last.date()), "counts": counts, "gate": gate, "per_event_bhar": res_ev,
                                   "daily_profile_weighted": prof, "liquidity": liq, "ex_date_guard": exg, "deposit_leg_information_only": deposit,
                                   "book": {"turnover_per_year": bk["hedged"][1], "long_only": explore.stats(cut(bk["long_only"][0])),
                                            "funds_long_per_active_day_mean": float((long_w.loc[start:] > 0).sum(axis=1).replace(0, np.nan).mean()),
                                            "share_of_sessions_active": float(((long_w.loc[start:] > 0).sum(axis=1) > 0).mean()),
                                            "median_adv_of_held_usd": float(held_adv.median())}})
    explore.write(HERE, res, pnl, title=f"Long CEFs in sessions T+2..T+11 after a holder UIT's termination date, against all CEFs; shift(2), gross; to {last.date()}",
                  controls={"controls, same book": cut(cb["hedged"][0])})
    if not SHUFFLE:
        for j in range(N_PEERS):                                                  # for checks.py (added 2026-11-18; changes no figure)
            E[f"peer{j}"] = peers[:, j]
        E.drop(columns=["trusts"]).to_parquet(OUT / "events.parquet")            # licensed-derived rows: outside the repository
    print(explore.table(res))
    for k in WINDOWS:
        t = res_ev["weighted_by_n_series"][k]
        print(k, {kk: (round(v.get("mean_bp", float("nan")), 1), round(v.get("median_bp", float("nan")), 1), round(v.get("share_positive", float("nan")), 3),
                       round(v.get("t_clustered") or float("nan"), 2), v["n"]) for kk, v in t.items()})
    print(json.dumps(liq, indent=1)); print(json.dumps(res["book"], indent=1)); print(json.dumps(deposit, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
