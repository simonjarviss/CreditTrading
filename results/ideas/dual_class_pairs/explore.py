"""Explore: reversion of the gap between two share classes of one company.

    QUANTT_ENV_FILE=<env> python3 results/ideas/dual_class_pairs/stage.py monthly
    QUANTT_ENV_FILE=<env> python3 results/ideas/dual_class_pairs/stage.py daily
    python3 results/ideas/dual_class_pairs/explore.py

WHY: two classes of one company's common stock (voting and non-voting, A and B) are claims
on the same cash flows, so the gap between them should not wander far. In small companies
one class is thin, the gap does wander, and a large fund cannot trade it. Schultz and Shive
(2010, docs/REFERENCES.md) report profits after costs on intraday quotes. This desk cannot
act intraday: it decides after a close and fills at the next close. The question here is
whether anything is left at that speed.

FIXED BEFORE ANY RETURN WAS READ (2026-11-16). Read first: the count of pairs (245 on 158
issuers, 48 to 115 alive a year), their tickers, class labels and median dollar volumes.
Reading the list showed that a shared CRSP issuer key also joins TRACKING stocks (Liberty's
groups, AT&T and Liberty Media, GM and GM class H, Genzyme's divisions), which are claims
on different businesses. CRSP carries no flag for them, so the GATE below was added before
any return was read.
  PAIRS     stage.py: two common-share permnos of one permco alive together for 12 months
            or more, 1999-2025, delisted ones included.
  SPREAD    s = cumulative sum of (log total return of A less log total return of B), so
            splits and dividends do not break it. It is read only on sessions when BOTH
            classes traded (volume above zero): a thin class's last price may be hours old.
  SIGNAL    at the close of t: dev = s[t] less the mean of s over the 60 sessions BEFORE t
            (both-traded sessions only, at least 40 of them); z = dev over the standard
            deviation of the same 60 sessions. Nothing dated t enters the mean or the
            deviation scale (asserted below).
  GATE      real pairs only: correlation of the two classes' 5-session log returns over the
            250 sessions before t (at least 120) of 0.90 or more. Two classes of one
            company pass; tracking stocks do not. Reported without the gate as well.
  ELIGIBLE  at t, both legs: price $2 or more, 21-session average dollar volume $100,000 or
            more, traded at t; and |dev| at least the sum of the two legs' median quoted
            closing spreads over the 21 sessions before t (a gap smaller than the cost of
            crossing both spreads is not a signal; no quote, no trade).
  ENTRY     |z| >= 2.0, the two-standard-deviation opening of Gatev, Goetzmann and
            Rouwenhorst (2006). Short the rich class, long the cheap one, equal dollars.
  EXIT      first of: z back to or through zero on a both-traded session; 20 sessions since
            entry (one month; the 60-session mean will have moved a third of the way to a
            permanent shift by then); a leg stops having CRSP rows. No re-entry on the exit day.
  WEIGHTS   5% of the book on each leg of each open pair; scaled down pro rata if more than
            20 pairs are open, so neither side exceeds 100%. Decided at t, filled at the
            close of t+1, earning from t+2 (harness.evaluate).
  CONTROLS  (1) PSEUDO-PAIRS: class A kept, class B replaced each year by a different
            company of the same two-digit SIC code nearest in market value the December
            before (stage.py). Same rule, no gate. If the result is ordinary short-term
            reversal between similar stocks, this scores as well.
            (2) STALE: the real book's positions applied 21 sessions late.
  CHECKS NAMED IN ADVANCE: positions one session late (skip day); the whole test on
            closing MID quotes (signal and returns), which removes bid-ask bounce and stale
            last trades; trades where the SHORT leg is the more liquid class and trades at
            least $1M a day (the only ones a borrow is plausible for), against the rest;
            buy-and-hold return per trade.
  EXPECTED  positive on closing prices and above both controls; smaller on mid quotes. If
            the mid-quote book is not above zero the closing-price result is bounce.
Gross; no cost or borrow is modelled. Aggregates only are written to results.json.
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
RES = Path.home() / "quantt_research" / "dual_class_pairs"
WIN, MIN_OBS, ENTRY, MAX_HOLD = 60, 40, 2.0, 20
MIN_PRICE, MIN_ADV, LEG_W, MAX_PAIRS = 2.0, 100_000.0, 0.05, 20
GATE_WIN, GATE_MIN, GATE_CORR = 250, 120, 0.90
LIQUID_SHORT_ADV = 1_000_000.0
FIRST = "2000-01-01"


def load() -> dict:
    d = pd.read_parquet(RES / "daily.parquet")
    d["date"] = pd.to_datetime(d["date"])
    d["prc"] = d["prc"].abs()
    w = {c: d.pivot(index="date", columns="permno", values=c) for c in ("ret", "prc", "vol", "dollar_volume", "bid", "ask")}
    ok = (w["bid"] > 0) & (w["ask"] >= w["bid"]) & (w["ask"] / w["bid"] <= 1.5)
    mid = ((w["bid"] + w["ask"]) / 2).where(ok)
    w["relspr"] = ((w["ask"] - w["bid"]) / mid).where(ok)
    # mid-quote return: the CRSP total return re-based from last price to closing mid on both days.
    # Where a day has no usable quote the CRSP price itself stands in (q = 1); the share is reported.
    q = (mid / w["prc"]).where(ok)
    w["has_quote"] = q.notna()
    q = q.fillna(1.0)
    w["ret_mid"] = ((1 + w["ret"]) * q / q.shift(1).fillna(1.0) - 1).where(w["ret"].notna())
    w["traded"] = (w["vol"] > 0) & w["ret"].notna()
    w["adv"] = w["dollar_volume"].rolling(21, min_periods=15).mean()
    w["spr21"] = w["relspr"].rolling(21, min_periods=10).median().shift(1)      # the 21 sessions BEFORE t
    return w


def signals(w: dict, ret: pd.DataFrame, ia: np.ndarray, ib: np.ndarray, *, gate: bool) -> dict:
    """z, eligibility and presence for pairs (columns ia[k], ib[k] of the wide frames)."""
    la = np.log1p(ret.to_numpy())
    A, B = la[:, ia], la[:, ib]
    present = np.isfinite(A) & np.isfinite(B)
    S = np.cumsum(np.nan_to_num(A) - np.nan_to_num(B), axis=0)
    tr = w["traded"].to_numpy()
    both = tr[:, ia] & tr[:, ib] & present
    Sv = pd.DataFrame(np.where(both, S, np.nan))
    prior = Sv.shift(1)                                    # strictly before t
    mean = prior.rolling(WIN, min_periods=MIN_OBS).mean().to_numpy()
    sd = prior.rolling(WIN, min_periods=MIN_OBS).std().to_numpy()
    dev = np.where(both, S - mean, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(sd > 0, dev / sd, np.nan)
    prc, adv, spr = w["prc"].to_numpy(), w["adv"].to_numpy(), w["spr21"].to_numpy()
    cost = spr[:, ia] + spr[:, ib]
    liquid = (prc[:, ia] >= MIN_PRICE) & (prc[:, ib] >= MIN_PRICE) & (adv[:, ia] >= MIN_ADV) & (adv[:, ib] >= MIN_ADV) & both
    elig = liquid & np.isfinite(cost) & (np.abs(dev) >= cost)
    corr = None
    if gate:
        a5 = pd.DataFrame(np.where(np.isfinite(A), A, np.nan)).rolling(5).sum()
        b5 = pd.DataFrame(np.where(np.isfinite(B), B, np.nan)).rolling(5).sum()
        corr = a5.rolling(GATE_WIN, min_periods=GATE_MIN).corr(b5).shift(1).to_numpy()
        passed = np.nan_to_num(corr, nan=-1.0) >= GATE_CORR
        liquid, elig = liquid & passed, elig & passed
    # alignment: the mean used at t is reproducible from s on sessions before t alone
    rng = np.random.default_rng(0)
    cols = np.flatnonzero(np.isfinite(mean).any(axis=0))
    for k in rng.choice(cols, size=min(5, len(cols)), replace=False):
        t = int(rng.choice(np.flatnonzero(np.isfinite(mean[:, k]))))
        past = Sv.iloc[max(0, t - WIN):t, k].dropna()
        assert abs(past.mean() - mean[t, k]) < 1e-9, "trailing mean uses data dated t or later"
    return {"z": z, "dev": dev, "elig": elig, "liquid": liquid, "both": both, "present": present, "cost": cost}


def simulate(sig: dict, allowed: np.ndarray | None = None) -> tuple[np.ndarray, list]:
    """Positions decided each day: +1 long A / short B, -1 the reverse, 0 flat. Trades (pair, entry, exit, side)."""
    z, elig, both, present = sig["z"], sig["elig"], sig["both"], sig["present"]
    T, P = z.shape
    if allowed is not None:
        elig = elig & allowed
    pos = np.zeros((T, P), dtype=np.int8)
    trades = []
    with np.errstate(invalid="ignore"):
        cand_all = elig & (np.abs(z) >= ENTRY)
    for p in np.flatnonzero(cand_all.any(axis=0)):
        free = 0
        for e in np.flatnonzero(cand_all[:, p]):
            if e < free:
                continue
            side = -int(np.sign(z[e, p]))
            x = T
            for t in range(e + 1, T):
                if (not present[t, p]) or (allowed is not None and not allowed[t, p]) or t - e >= MAX_HOLD \
                        or (both[t, p] and np.isfinite(z[t, p]) and side * z[t, p] >= 0):
                    x = t
                    break
            pos[e:x, p] = side
            trades.append((int(p), int(e), int(x), side))
            free = x + 1
    return pos, trades


def pos_from(trades: list, shape: tuple) -> np.ndarray:
    pos = np.zeros(shape, dtype=np.int8)
    for p, e, x, side in trades:
        pos[e:x, p] = side
    return pos


def book(pos: np.ndarray, ia: np.ndarray, ib: np.ndarray, R: pd.DataFrame, lag: int = 0) -> tuple[pd.Series, dict]:
    """Pair positions -> security weights -> harness P&L. `lag` applies the positions that many sessions late."""
    n = np.abs(pos).sum(axis=1)
    scale = np.minimum(1.0, MAX_PAIRS / np.maximum(n, 1))
    W = pos * LEG_W * scale[:, None]
    H = np.zeros(R.shape)
    for p in np.flatnonzero(np.abs(pos).any(axis=0)):
        H[:, ia[p]] += W[:, p]
        H[:, ib[p]] -= W[:, p]
    Hd = pd.DataFrame(H, index=R.index, columns=R.columns)
    if lag:
        Hd = Hd.shift(lag).fillna(0.0)
    res = harness.evaluate(Hd, R.fillna(0.0))
    held = harness.held(Hd)
    miss = int(((held != 0) & R.isna()).sum().sum())
    pnl = res["pnl"].loc[FIRST:]
    gross = Hd.abs().sum(axis=1).loc[FIRST:]
    return pnl, {"turnover_per_year": float(res["turn_series"].loc[FIRST:].mean() * 252), "mean_gross": float(gross.mean()),
                 "mean_open_pairs": float(pd.Series(n, index=R.index).loc[FIRST:].mean()),
                 "share_days_invested": float((gross > 0).mean()),
                 "held_leg_days": int((held != 0).sum().sum()), "held_leg_days_without_return": miss}


def trade_table(trades: list, sig: dict, w: dict, ia, ib, dates) -> pd.DataFrame:
    """One row per trade with what was known at entry, and the buy-and-hold result of each leg."""
    Rc, Rm = w["ret"].fillna(0.0).to_numpy(), w["ret_mid"].fillna(0.0).to_numpy()
    adv, spr, prc = w["adv"].to_numpy(), w["spr21"].to_numpy(), w["prc"].to_numpy()
    T = len(dates)
    rows = []
    for p, e, x, side in trades:
        lo, sh = (ia[p], ib[p]) if side > 0 else (ib[p], ia[p])
        a, b = e + harness.EXEC_LAG, min(x + harness.EXEC_LAG, T)      # returns earned: e+2 .. x+1
        if a >= T:
            continue
        r = {"pair": p, "entry": dates[e], "exit_decided": dates[min(x, T - 1)], "sessions_held": b - a, "absz": abs(sig["z"][e, p]),
             "absdev": abs(sig["dev"][e, p]), "cost": sig["cost"][e, p], "adv_long": adv[e, lo], "adv_short": adv[e, sh],
             "spr_long": spr[e, lo], "spr_short": spr[e, sh], "prc_long": prc[e, lo], "prc_short": prc[e, sh]}
        for tag, R in (("close", Rc), ("mid", Rm)):
            r[f"long_{tag}"] = float(np.prod(1 + R[a:b, lo]) - 1)
            r[f"short_{tag}"] = float(np.prod(1 + R[a:b, sh]) - 1)
            r[f"bh_{tag}"] = r[f"long_{tag}"] - r[f"short_{tag}"]
        rows.append(r)
    return pd.DataFrame(rows)


def trade_stats(t: pd.DataFrame) -> dict:
    if t.empty:
        return {"trades": 0}
    out = {"trades": int(len(t)), "pairs_traded": int(t["pair"].nunique()), "median_sessions_held": float(t["sessions_held"].median())}
    for tag in ("close", "mid"):
        x = t[f"bh_{tag}"]
        out[f"bh_{tag}_mean_bp"] = float(x.mean() * 1e4); out[f"bh_{tag}_median_bp"] = float(x.median() * 1e4)
        out[f"bh_{tag}_hit"] = float((x > 0).mean()); out[f"bh_{tag}_t"] = float(x.mean() / x.std() * np.sqrt(len(x))) if len(x) > 2 else None
        out[f"long_leg_{tag}_mean_bp"] = float(t[f"long_{tag}"].mean() * 1e4)
        out[f"short_leg_{tag}_mean_bp"] = float(t[f"short_{tag}"].mean() * 1e4)
    out.update({"median_abs_dev_bp": float(t["absdev"].median() * 1e4), "median_two_leg_spread_bp": float(t["cost"].median() * 1e4),
                "median_spread_long_bp": float(t["spr_long"].median() * 1e4), "median_spread_short_bp": float(t["spr_short"].median() * 1e4),
                "median_adv_thinner_leg_usd": float(t[["adv_long", "adv_short"]].min(axis=1).median()),
                "median_adv_long_usd": float(t["adv_long"].median()), "median_adv_short_usd": float(t["adv_short"].median()),
                "median_price_long": float(t["prc_long"].median()), "median_price_short": float(t["prc_short"].median()),
                "share_short_leg_is_thinner": float((t["adv_short"] < t["adv_long"]).mean())})
    return out


def brief(pnl: pd.Series) -> dict:
    s = explore.summarise(pnl)
    return {"sharpe": s["full"]["sharpe"], "t": s["full"]["t"], "ann_ret": s["full"]["ann_ret"], "ann_vol": s["full"]["ann_vol"],
            "max_drawdown": s["full"]["max_drawdown"], "halves": [s["early_half"]["sharpe"], s["late_half"]["sharpe"]],
            "eras": {k: v["sharpe"] for k, v in s["eras"].items()}, "eras_ann_ret": {k: v["ann_ret"] for k, v in s["eras"].items()}}


def show(name: str, b: dict, info: dict | None = None) -> None:
    f = lambda v: "n/a" if v is None else f"{v:.2f}"
    print(f"{name:<46} SR {f(b['sharpe'])} (t {f(b['t'])})  {b['ann_ret']:+.2%} / {b['ann_vol']:.2%}  halves {f(b['halves'][0])} / {f(b['halves'][1])}  "
          + "  ".join(f"{k[2:4]}-{k[7:]}: {f(v)}" for k, v in b["eras"].items())
          + (f"  | turn {info['turnover_per_year']:.1f}/yr, gross {info['mean_gross']:.2f}, open {info['mean_open_pairs']:.1f}" if info else ""))


def main() -> int:
    w = load()
    dates = w["ret"].index
    col = {p: i for i, p in enumerate(w["ret"].columns)}
    pairs = pd.read_parquet(RES / "pairs.parquet")
    ctl = pd.read_parquet(RES / "controls.parquet")
    ia = np.array([col[p] for p in pairs["permno_a"]]); ib = np.array([col[p] for p in pairs["permno_b"]])
    out = {"panel_first_date": str(dates[0].date()), "panel_last_date": str(dates[-1].date()), "first_scored": FIRST,
           "fixed": {"window": WIN, "min_obs": MIN_OBS, "entry_z": ENTRY, "max_hold": MAX_HOLD, "min_price": MIN_PRICE, "min_adv": MIN_ADV,
                     "leg_weight": LEG_W, "max_pairs": MAX_PAIRS, "gate_corr": GATE_CORR, "gate_window": GATE_WIN},
           "pairs_in_crsp": int(len(pairs)), "issuers": int(pairs["permco"].nunique())}
    R, Rm = w["ret"], w["ret_mid"]
    yr = pd.Series(dates.year, index=dates)

    # ---- the pre-specified book -------------------------------------------------------------
    sig = signals(w, R, ia, ib, gate=True)
    pos, trades = simulate(sig)
    pnl, info = book(pos, ia, ib, R)
    tt = trade_table(trades, sig, w, ia, ib, dates)
    tt = tt[tt["entry"] >= FIRST]
    live = pd.DataFrame(sig["liquid"], index=dates).sum(axis=1).groupby(yr).mean()
    ever = pd.DataFrame(sig["liquid"], index=dates).groupby(yr).any().sum(axis=1)
    ntr = tt.groupby(tt["entry"].dt.year).size()
    out["pairs_by_year"] = {int(y): {"passing_gate_and_floors_mean_per_day": round(float(live.get(y, 0)), 1),
                                     "passing_on_any_day": int(ever.get(y, 0)), "trades": int(ntr.get(y, 0))} for y in range(2000, dates[-1].year + 1)}
    print("pairs passing the gate and floors (mean a day / any day / trades), by year:")
    print("  " + ", ".join(f"{y}: {v['passing_gate_and_floors_mean_per_day']}/{v['passing_on_any_day']}/{v['trades']}" for y, v in out["pairs_by_year"].items()))
    full = explore.summarise(pnl)
    print("\n== REAL PAIRS, closing prices (pre-specified)")
    print(explore.table(full))
    q_share = float(w["has_quote"].to_numpy()[(harness.held(pd.DataFrame(pos)).to_numpy() != 0).any(axis=1)].mean())
    out["REAL"] = {**info, **full, "trade_stats": trade_stats(tt)}
    print(json.dumps(out["REAL"]["trade_stats"], indent=1))
    books = {"REAL": pnl}
    rows = {}

    def add(name, p, i=None, trades_df=None):
        b = brief(p)
        rows[name] = {**b, **(i or {}), **({"trade_stats": trade_stats(trades_df)} if trades_df is not None else {})}
        books[name] = p
        show(name, b, i)

    print()
    add("REAL", pnl, info)
    # ---- controls ---------------------------------------------------------------------------
    p_, i_ = book(pos, ia, ib, R, lag=21); add("control: positions 21 sessions late", p_, i_)
    cu = ctl.groupby(["permno_a", "match"])["year"].apply(set).reset_index()
    cu = cu[cu["permno_a"].isin(col) & cu["match"].isin(col)]
    ca = np.array([col[p] for p in cu["permno_a"]]); cb = np.array([col[p] for p in cu["match"]])
    allowed = np.column_stack([np.isin(dates.year, list(s)) for s in cu["year"]])
    csig = signals(w, R, ca, cb, gate=False)
    cpos, ctr = simulate(csig, allowed)
    p_, i_ = book(cpos, ca, cb, R)
    ctt = trade_table(ctr, csig, w, ca, cb, dates); ctt = ctt[ctt["entry"] >= FIRST]
    add("control: pseudo-pairs (matched other company)", p_, i_, ctt)
    usig = signals(w, R, ia, ib, gate=False)
    upos, utr = simulate(usig)
    p_, i_ = book(upos, ia, ib, R)
    utt = trade_table(utr, usig, w, ia, ib, dates); utt = utt[utt["entry"] >= FIRST]
    add("real pairs WITHOUT the gate (tracking stocks in)", p_, i_, utt)
    # ---- checks named in advance ------------------------------------------------------------
    p_, i_ = book(pos, ia, ib, R, lag=1); add("check: positions one session late (skip day)", p_, i_)
    p_, i_ = book(pos, ia, ib, Rm); add("check: same positions, scored on mid quotes", p_, i_)
    msig = signals(w, Rm, ia, ib, gate=True)
    mpos, mtr = simulate(msig)
    p_, i_ = book(mpos, ia, ib, Rm)
    mtt = trade_table(mtr, msig, w, ia, ib, dates); mtt = mtt[mtt["entry"] >= FIRST]
    add("check: MID quotes for signal and returns", p_, i_, mtt)
    p_, i_ = book(mpos, ia, ib, Rm, lag=1); add("check: MID quotes, one session late", p_, i_)
    cmsig = signals(w, Rm, ca, cb, gate=False)
    cmpos, _ = simulate(cmsig, allowed)
    p_, i_ = book(cmpos, ca, cb, Rm); add("control: pseudo-pairs on MID quotes", p_, i_)
    for label, tb, trl, sg in (("close", tt, trades, sig), ("MID", mtt, mtr, msig)):
        Ruse = R if label == "close" else Rm
        key = {(r.pair, r.entry) for r in tb[(tb["adv_short"] >= tb["adv_long"]) & (tb["adv_short"] >= LIQUID_SHORT_ADV)].itertuples()}
        easy = [t for t in trl if (t[0], dates[t[1]]) in key]
        hard = [t for t in trl if (t[0], dates[t[1]]) not in key]
        for nm, sub in ((f"{label}: SHORT leg is the liquid class (>= $1M)", easy), (f"{label}: short leg is the thin class (the rest)", hard)):
            sp = pos_from(sub, pos.shape)
            p_, i_ = book(sp, ia, ib, Ruse)
            st = trade_table(sub, sg, w, ia, ib, dates); st = st[st["entry"] >= FIRST] if len(st) else st
            add(nm, p_, i_, st)
    d = (books["REAL"] - books["control: pseudo-pairs (matched other company)"]).dropna()
    add("REAL less pseudo-pairs", d)
    d = (books["check: MID quotes for signal and returns"] - books["control: pseudo-pairs on MID quotes"]).dropna()
    add("MID less pseudo-pairs on MID", d)
    out["rows"] = rows
    out["share_of_sessions_with_a_closing_quote_all_securities"] = float(w["has_quote"].to_numpy()[w["ret"].notna().to_numpy()].mean())
    out["note_quote_share_on_held_days"] = q_share
    by = tt.groupby(tt["entry"].dt.year).agg(trades=("bh_close", "size"), bh_close_bp=("bh_close", lambda x: x.mean() * 1e4),
                                             bh_mid_bp=("bh_mid", lambda x: x.mean() * 1e4))
    out["trades_by_year"] = {int(y): {k: float(v) for k, v in r.items()} for y, r in by.iterrows()}
    explore.write(HERE, out, pnl, title="Share-class pairs: reversion of the gap, closing prices, gross, shift(2)",
                  controls={k: books[k] for k in ("control: pseudo-pairs (matched other company)", "control: positions 21 sessions late",
                                                  "check: MID quotes for signal and returns")})
    tt.to_parquet(RES / "trades_close.parquet"); mtt.to_parquet(RES / "trades_mid.parquet")       # licensed rows: outside the repo
    return 0


if __name__ == "__main__":
    sys.exit(main())
