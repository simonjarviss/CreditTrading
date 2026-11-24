"""Explore: is there a dated buyer in closed-end funds around the PAYMENT date (reinvestment plans)?

    python3 scripts/research/stage_crsp_cefs.py                              (QUANTT_ENV_FILE set)
    python3 results/ideas/cef_drip_paydate/stage.py r2                       (QUANTT_ENV_FILE set)
    python3 results/ideas/cef_drip_paydate/stage.py yahoo
    python3 results/ideas/cef_drip_paydate/explore.py

THE MECHANISM. Most closed-end funds run a dividend-reinvestment plan. When the fund trades
BELOW net asset value the plan agent buys the reinvested shares in the open market, starting
on or just after the payment date; at a premium the fund issues new shares and nobody buys.
Agenda item B3 (results/cef/RESEARCH_AGENDA_2026-10-08.md) named this and was never run; the
turn-of-month screen of 2026-11-02 saw no discount/premium gap on 17 credit funds around the
month END (results/cef/screens_2026-11-02/UNIQUE_ANGLES.md), but it never used a pay date.

FIXED BEFORE ANY RETURN WAS READ (only counts, the ex-to-pay gap and NAV coverage were read)
  universe   every closed-end fund on CRSP, dead ones included (stage_crsp_cefs.py).
  event      a regular cash distribution in CRSP `stkdistributions`: distype CD, ordinary,
             paid in USD, frequency monthly or quarterly, amount > 0. Several rows of one fund
             with one payment date are one event (amounts summed). P = the first session on or
             after `dispaydt`.
  known      the event is used only if it was public by the decision: the session after
             CRSP's declaration date (CRSP is a median of one session late) must be on or
             before the decision session P-3. Where CRSP has no declaration date the ex-date
             session stands in for it (a payment date is public by the ex-date at the latest).
  eligible   at the decision session P-3: price >= $2 and 21-session average dollar volume
             >= $500,000 (the ex-date card's filter), and the fund has a row that day.
  trade      decide at P-3, fill at the close of P-2, hold to the close of P+5: the book earns
             the seven sessions P-1 .. P+5. shift(2) on the canonical harness.
  main book  +0.5 split equally across funds in a window, -0.5 split equally across EVERY
             eligible fund (the equal-weighted CEF market, event funds included). Flat on a day
             with no fund in a window.
  splits     (a) FLOW: reinvested dollars = amount x shares outstanding x 20% participation
                 (ASSUMED [U]; only the ranking matters), over the 21-session average dollar
                 volume, at P-3. Top third long against bottom third short; breakpoints are
                 the terciles of the PREVIOUS calendar year's eligible events (no lookahead).
             (b) DISCOUNT, the sharp test: price / NAV - 1 at P-4 (one session before the
                 decision, so the NAV was published). Long funds below NAV in their window,
                 short funds at or above NAV in theirs. Also a "clear" version: at least 2%
                 below against at least 2% above. NAVs exist for funds alive at the panel's
                 end only (desk panels, Yahoo), so this split is on survivors; the price-only
                 main book on all funds is beside it.
             (c) MONTH TURN: P within the last two or first two sessions of a month, against
                 any other P, because the desk already knows CEFs rise at the month turn and
                 most funds pay there.
             (d) the ex-to-pay gap in sessions, in buckets.
  controls   the same book with every P moved ten sessions EARLIER and ten LATER. For a monthly
             payer both sit near an ex-date, so a second control removes that cycle directly:
             the event-time profile and the per-event figure are recomputed with every
             fund-day within three sessions of one of the fund's own ex-dates blanked, in the
             event funds and in the benchmark.
  profile    mean return less the equal-weighted eligible universe by session, P-10 .. P+10.
  per event  buy-and-hold, close of P-2 to close of P+5, fund less the equal-weighted
             universe compounded over the same sessions: mean, median, share positive, t
             clustered by pay month. Repeated on closing MID quotes (bid-ask bounce).
  expected   if plan buying moves prices: a positive relative return from P to P+5, larger in
             the top flow third, present in discount funds and ABSENT in premium funds. If the
             idea is wrong the discount and premium funds score the same and any pay-date
             excess is the month turn or the ex-date cycle.

Returns are CRSP total returns (a distribution is in the return on its ex-date, so the ex-day
price drop is not read as a signal). Gross: no cost, no borrow.
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
HERE = Path(__file__).resolve().parent
ROOT = Path.home() / "quantt_research"
STAGE = ROOT / "cef_drip_paydate"
PANEL = ROOT / "crsp_cef_daily.parquet"
DESK_DATA = Path("/Users/simonjarvis/Downloads/2027/Projects/Quant - PM2027/2027/data")   # main checkout, read-only
DESK_NAV = (DESK_DATA / "cef" / "cef_nav.parquet", DESK_DATA / "cef_families" / "cef_nav.parquet")

MIN_PRICE, MIN_ADV = 2.0, 500_000.0
DECIDE, LAST = -3, 5                 # decide at P-3; earn P-1 .. P+5
EARN = range(DECIDE + harness.EXEC_LAG, LAST + 1)
PARTICIPATION = 0.20                 # ASSUMED [U]; scales the flow share, never its ranking
EX_BLANK = 3                         # sessions either side of an own ex-date removed in the ex-clean control
MIN_SIDE = 3                         # a long-short split is flat with fewer names on either side
PROFILE = range(-10, 11)
assert harness.EXEC_LAG == 2


def load() -> dict:
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    q = pd.read_parquet(STAGE / "crsp_cef_quotes.parquet")
    q["date"] = pd.to_datetime(q["date"])
    piv = lambda d, v: d.pivot(index="date", columns="permno", values=v)
    out = {k: piv(df, k) for k in ("ret", "prc", "cap", "dollar_volume", "div")}
    cols, idx = out["ret"].columns, out["ret"].index
    for k in ("bid", "ask", "vol"):
        out[k] = piv(q, k).reindex(index=idx, columns=cols)
    out["ticker_last"] = df[df["date"] == idx[-1]].dropna(subset=["ticker"]).set_index("ticker")["permno"]
    return out


def load_nav(ticker_last: pd.Series, idx: pd.DatetimeIndex, cols: pd.Index) -> tuple[pd.DataFrame, dict]:
    """Daily NAV by permno. A NAV series is attached ONLY to the permno that holds its ticker on
    the panel's last date: tickers are reused, and a 2004 fund with today's ticker is not this fund."""
    parts = [pd.read_parquet(f)[["date", "nav", "ticker"]] for f in DESK_NAV]
    ydir = STAGE / "yahoo_nav"
    yfiles = sorted(ydir.glob("*.parquet"))
    if not yfiles:
        raise FileNotFoundError(f"no Yahoo NAV files in {ydir}: run stage.py yahoo")
    parts += [pd.read_parquet(f)[["date", "nav", "ticker"]] for f in yfiles]
    nav = pd.concat(parts, ignore_index=True)
    nav["date"] = pd.to_datetime(nav["date"])
    n_tickers = nav["ticker"].nunique()
    nav = nav[nav["ticker"].isin(ticker_last.index) & (nav["nav"] > 0)]
    nav["permno"] = nav["ticker"].map(ticker_last)
    nav = nav.drop_duplicates(["date", "permno"], keep="last")
    wide = nav.pivot(index="date", columns="permno", values="nav").reindex(index=idx, columns=cols)
    return wide, {"nav_tickers_read": int(n_tickers), "nav_funds_matched_to_a_live_permno": int(nav["permno"].nunique()),
                  "desk_panel_tickers": int(sum(pd.read_parquet(f)["ticker"].nunique() for f in DESK_NAV)),
                  "yahoo_tickers": len(yfiles)}


def events(idx: pd.DatetimeIndex, cols: pd.Index) -> tuple[pd.DataFrame, dict]:
    d = pd.read_parquet(STAGE / "stkdist_cef_raw.parquet")
    n_raw = len(d)
    d = d[(d["distype"] == "CD") & (d["disordinaryflg"] == "Y") & (d["dispaymenttype"] == "USD")
          & d["disfreqtype"].isin(["M", "Q"]) & (d["disdivamt"] > 0) & d["dispaydt"].notna() & d["permno"].isin(cols)]
    n_regular = len(d)
    # NaT.max() over a group with any missing declaration stays missing only if ALL are missing;
    # a group with one missing declaration is treated as missing (min_count), so nothing is assumed known.
    g = d.groupby(["permno", "dispaydt"], as_index=False).agg(
        amt=("disdivamt", "sum"), ex=("disexdt", "max"), n_rows=("disdivamt", "size"),
        decl=("disdeclaredt", "max"), decl_missing=("disdeclaredt", lambda s: s.isna().any()),
        freq=("disfreqtype", "first"))
    g.loc[g["decl_missing"], "decl"] = pd.NaT
    pos = lambda s: idx.searchsorted(pd.to_datetime(s).values, side="left")      # first session ON OR AFTER the date
    g["iP"], g["iX"] = pos(g["dispaydt"]), pos(g["ex"])
    # known: session after the declaration; without a declaration date, the ex-date session
    g["iK"] = np.where(g["decl"].notna(), pos(g["decl"].fillna(pd.Timestamp("1990-01-01"))) + 1, g["iX"])
    n = len(idx)
    inside = (g["iP"] + min(PROFILE) >= 0) & (g["iP"] + LAST < n) & (g["dispaydt"] <= idx[-1])
    g = g[inside].copy()
    g["iD"] = g["iP"] + DECIDE
    g["known"] = g["iK"] <= g["iD"]
    g["j"] = cols.get_indexer(g["permno"])
    assert (g["j"] >= 0).all()
    g["gap"] = g["iP"] - g["iX"]
    return g.reset_index(drop=True), {"distribution_rows_cef": int(n_raw), "regular_cash_rows": int(n_regular),
                                      "pay_date_events": int(len(g)), "declaration_missing": int(g["decl_missing"].sum()),
                                      "not_known_by_decision": int((~g["known"]).sum())}


def window_matrix(shape, i_pay: np.ndarray, j: np.ndarray, shift: int = 0) -> np.ndarray:
    """DECISION-time flags: true at t for a fund whose window is earned at t+2, i.e. t in P-3 .. P+3."""
    m = np.zeros(shape, dtype=bool)
    for k in EARN:
        t = i_pay + shift + k - harness.EXEC_LAG
        ok = (t >= 0) & (t < shape[0])
        m[t[ok], j[ok]] = True
    return m


def ls_book(long_: np.ndarray, short: np.ndarray, idx, cols, min_side: int = 1) -> pd.DataFrame:
    """+0.5 equally across `long_`, -0.5 equally across `short`, netted; flat unless both sides have min_side."""
    nl, ns = long_.sum(axis=1), short.sum(axis=1)
    on = (nl >= min_side) & (ns >= min_side)
    w = np.zeros(long_.shape)
    w[on] = 0.5 * long_[on] / nl[on, None] - 0.5 * short[on] / ns[on, None]
    return pd.DataFrame(w, index=idx, columns=cols)


def cluster_t(v: np.ndarray, g: np.ndarray) -> dict:
    """Mean with a t that treats every event in one pay month as one observation's worth of noise."""
    ok = np.isfinite(v)
    v, g = v[ok], g[ok]
    if len(v) < 30:
        return {"n": int(len(v))}
    m = v.mean()
    s = pd.Series(v - m).groupby(g).sum()
    se = np.sqrt((s ** 2).sum()) / len(v)
    return {"n": int(len(v)), "mean_bp": float(m * 1e4), "median_bp": float(np.median(v) * 1e4),
            "share_positive": float((v > 0).mean()), "t_clustered_by_month": float(m / se), "clusters": int(len(s))}


def main() -> int:
    P = load()
    ret, prc, cap, dv = P["ret"], P["prc"], P["cap"], P["dollar_volume"]
    idx, cols = ret.index, ret.columns
    last = idx[-1].date()
    n, m = ret.shape
    ev, counts = events(idx, cols)
    nav, nav_info = load_nav(P["ticker_last"], idx, cols)

    adv = dv.rolling(21, min_periods=10).mean()
    elig = ((prc >= MIN_PRICE) & (adv >= MIN_ADV)).to_numpy()            # dated t: usable by a decision at t
    R = ret.fillna(0.0)                                                   # no row = stopped trading (stage script)
    Rn = ret.to_numpy()
    uni = np.nanmean(np.where(elig_prev := np.vstack([np.zeros((harness.EXEC_LAG, m), bool), elig[:-harness.EXEC_LAG]]), Rn, np.nan), axis=1)
    # ALIGNMENT. `elig_prev[s]` is eligibility dated s-2: the benchmark for the return of session s
    # is the set of funds a decision two sessions earlier could have held, exactly what the book shorts.
    rel = Rn - uni[:, None]

    # ---- per-event attributes, all dated at or before the decision session iD = P-3 ------------
    iD, iP, j = ev["iD"].to_numpy(), ev["iP"].to_numpy(), ev["j"].to_numpy()
    assert (iD == iP + DECIDE).all() and (ev.loc[ev["known"], "iK"] <= ev.loc[ev["known"], "iD"]).all()
    ev["elig"] = elig[iD, j] & np.isfinite(Rn[iD, j])
    ev["use"] = ev["elig"] & ev["known"]
    shares = (cap * 1000.0 / prc).to_numpy()                             # CRSP cap is in $ thousands
    ev["adv"] = adv.to_numpy()[iD, j]
    ev["price"] = prc.to_numpy()[iD, j]
    ev["cap_musd"] = cap.to_numpy()[iD, j] / 1000.0
    ev["flow_share"] = ev["amt"].to_numpy() * shares[iD, j] * PARTICIPATION / ev["adv"]
    ev["yield_per_event"] = ev["amt"] / ev["price"]
    bid, ask = P["bid"].to_numpy(), P["ask"].to_numpy()
    good_q = (bid > 0) & (ask >= bid)
    mid = np.where(good_q, (bid + ask) / 2.0, np.nan)
    ev["spread"] = np.where(good_q[iD, j], (ask[iD, j] - bid[iD, j]) / mid[iD, j], np.nan)
    navn = nav.to_numpy()
    disc = prc.to_numpy() / navn - 1.0
    disc[(disc < -0.6) | (disc > 1.5)] = np.nan                          # a ratio out here is a bad match, not a discount
    ev["disc"] = disc[iD - 1, j]                                          # P-4: published before the P-3 decision
    ev["pay_year"] = idx[iP].year
    ev["pay_month"] = idx[iP].year * 100 + idx[iP].month
    mon = pd.Series(idx.year * 100 + idx.month, index=idx)
    k_from_end = mon.groupby(mon).cumcount(ascending=False).to_numpy()   # 0 = last session of its month
    k_from_start = mon.groupby(mon).cumcount().to_numpy()
    ev["month_turn"] = (k_from_end[iP] <= 1) | (k_from_start[iP] <= 1)
    use = ev[ev["use"]].copy()
    # flow terciles from the PREVIOUS calendar year's eligible events
    br = use.groupby("pay_year")["flow_share"].quantile([1 / 3, 2 / 3]).unstack()
    lo = use["pay_year"].map(br[1 / 3].shift(1)); hi = use["pay_year"].map(br[2 / 3].shift(1))
    use["flow_grp"] = np.where(lo.isna(), "none", np.where(use["flow_share"] >= hi, "top", np.where(use["flow_share"] <= lo, "bottom", "mid")))
    use["disc_grp"] = np.where(use["disc"].isna(), "none", np.where(use["disc"] < 0, "discount", "premium"))
    use["disc_clear"] = np.where(use["disc"] <= -0.02, "discount", np.where(use["disc"] >= 0.02, "premium", "none"))
    use["gap_grp"] = pd.cut(use["gap"], [-999, 7, 12, 17, 999], labels=["<=7", "8-12", "13-17", "18+"]).astype(str)

    # ---- calendar-time books on the harness -----------------------------------------------------
    def win(sub: pd.DataFrame, shift: int = 0) -> np.ndarray:
        return window_matrix((n, m), sub["iP"].to_numpy(), sub["j"].to_numpy(), shift)

    def run(H: pd.DataFrame) -> tuple[pd.Series, dict]:
        r = harness.evaluate(H, R)
        return r["pnl"].iloc[30:-harness.EXEC_LAG], r

    inw = win(use)
    H_main = ls_book(inw, elig, idx, cols)
    pnl, res_h = run(H_main)
    ctl = {"pay date moved 10 sessions earlier": run(ls_book(win(use, -10), elig, idx, cols))[0],
           "pay date moved 10 sessions later": run(ls_book(win(use, +10), elig, idx, cols))[0]}
    held_missing = int(((harness.held(H_main) != 0) & ret.isna()).sum().sum())

    def split(col: str, a: str, b: str) -> dict:
        la, sb = win(use[use[col] == a]), win(use[use[col] == b])
        out = {}
        for name, H in ((f"{a} less {b}", ls_book(la, sb, idx, cols, MIN_SIDE)),
                        (f"{a} against the market", ls_book(la, elig, idx, cols, MIN_SIDE)),
                        (f"{b} against the market", ls_book(sb, elig, idx, cols, MIN_SIDE))):
            p, _ = run(H)
            first = p.index[(p != 0).to_numpy().argmax()] if (p != 0).any() else p.index[0]
            s = explore.summarise(p.loc[first:])
            out[name] = {"full": s["full"], "early_half": s["early_half"]["sharpe"], "late_half": s["late_half"]["sharpe"],
                         "eras": {k: v["sharpe"] for k, v in s["eras"].items()},
                         "names_long_per_active_day": float(la.sum(axis=1)[la.sum(axis=1) > 0].mean()) if "less" in name or a in name.split(" against")[0] else float(sb.sum(axis=1)[sb.sum(axis=1) > 0].mean())}
        return out

    use["turn_grp"] = np.where(use["month_turn"], "month turn", "mid month")
    splits = {"flow share (top third / bottom third)": split("flow_grp", "top", "bottom"),
              "discount / premium (survivors only)": split("disc_grp", "discount", "premium"),
              "discount <= -2% / premium >= +2% (survivors only)": split("disc_clear", "discount", "premium"),
              "pay date at the month turn / mid month": split("turn_grp", "month turn", "mid month")}

    # ---- event time: profile and buy-and-hold ---------------------------------------------------
    exn = (P["div"].fillna(0.0) > 0).to_numpy()
    near_ex = np.zeros((n, m), bool)
    for k in range(-EX_BLANK, EX_BLANK + 1):
        near_ex |= np.roll(exn, k, axis=0) if k == 0 else (np.vstack([np.zeros((k, m), bool), exn[:-k]]) if k > 0 else np.vstack([exn[-k:], np.zeros((-k, m), bool)]))
    uni_clean = np.nanmean(np.where(elig_prev & ~near_ex, Rn, np.nan), axis=1)
    rel_clean = np.where(near_ex, np.nan, Rn - uni_clean[:, None])
    mid_ret = (1.0 + Rn) * (mid / prc.to_numpy()) / np.vstack([np.full((1, m), np.nan), (mid / prc.to_numpy())[:-1]]) - 1.0
    uni_mid = np.nanmean(np.where(elig_prev, mid_ret, np.nan), axis=1)

    def profile(sub: pd.DataFrame, relm: np.ndarray) -> dict:
        # FIX AFTER THE INTERRUPTION (2026-11-18): an event needs only P+5 inside the panel, so P+k for
        # k > 5 could index past the last row (a crash). Such a session is left out of that column.
        ip, jj, g = sub["iP"].to_numpy(), sub["j"].to_numpy(), sub["pay_month"].to_numpy()
        out = {}
        for k in PROFILE:
            ok = (ip + k >= 0) & (ip + k < n)
            out[f"P{k:+d}"] = cluster_t(relm[ip[ok] + k, jj[ok]], g[ok])
        return out

    def bh(sub: pd.DataFrame, r: np.ndarray, bench: np.ndarray, ks=EARN, skip_nan: bool = False) -> dict:
        ip, jj = sub["iP"].to_numpy(), sub["j"].to_numpy()
        f = np.ones(len(sub)); b = np.ones(len(sub)); bad = np.zeros(len(sub), bool)
        for k in ks:
            x = r[ip + k, jj]
            if skip_nan:                           # ex-clean: a blanked day earns nothing on either side
                keep = np.isfinite(x)
                f *= np.where(keep, 1.0 + x, 1.0); b *= np.where(keep, 1.0 + bench[ip + k], 1.0)
            else:
                bad |= ~np.isfinite(x)
                f *= 1.0 + np.where(np.isfinite(x), x, 0.0); b *= 1.0 + bench[ip + k]
        v = np.where(bad, np.nan, f - b)
        return cluster_t(v, sub["pay_month"].to_numpy())

    Rclean = np.where(near_ex, np.nan, Rn)

    def event_block(sub: pd.DataFrame) -> dict:
        return {"buy_and_hold_P-1_to_P+5": bh(sub, Rn, uni),
                "buy_and_hold_on_mid_quotes": bh(sub, mid_ret, uni_mid),
                "buy_and_hold_ex_windows_blanked": bh(sub, Rclean, uni_clean, skip_nan=True),
                "P-1_and_P": bh(sub, Rn, uni, ks=range(-1, 1)),
                "P+1_to_P+5": bh(sub, Rn, uni, ks=range(1, 6)),
                # FIX AFTER THE INTERRUPTION (2026-11-18): one event in the panel's first 11 sessions used to blank
                # the placebo for its whole group; such events are now dropped from the placebo instead.
                "placebo_window_at_P-10": bh(sub[sub["iP"] - 11 >= 0], Rn, uni, ks=[k - 10 for k in EARN]),
                "placebo_window_at_P+10": bh(sub[sub["iP"] + 15 < n], Rn, uni, ks=[k + 10 for k in EARN]),
                "median_adv_usd": float(sub["adv"].median()), "median_price": float(sub["price"].median()),
                "median_cap_musd": float(sub["cap_musd"].median()),
                "median_spread_bp": float(sub["spread"].median() * 1e4), "p75_spread_bp": float(sub["spread"].quantile(0.75) * 1e4),
                "median_flow_share_of_adv": float(sub["flow_share"].median()),
                "median_discount": float(sub["disc"].median()) if sub["disc"].notna().any() else None}

    groups = {"all": use}
    for col in ("flow_grp", "disc_grp", "turn_grp", "gap_grp", "freq"):
        for v, sub in use.groupby(col):
            if v != "none":
                groups[f"{col}={v}"] = sub
    for v, sub in use.groupby("disc_clear"):
        if v != "none":
            groups[f"disc_clear={v}"] = sub
    for a, b in explore.ERAS:
        sub = use[(idx[use["iP"]] >= a) & (idx[use["iP"]] <= b)]
        if len(sub):
            groups[f"era={a[:4]}-{min(int(b[:4]), last.year)}"] = sub
    by_group = {k: event_block(v) for k, v in groups.items()}
    # the sharp test inside the top flow third, and with a NAV but on ALL-fund price data for the bias bound
    for a in ("discount", "premium"):
        by_group[f"top flow third & {a}"] = event_block(use[(use["flow_grp"] == "top") & (use["disc_grp"] == a)])
    by_group["has a NAV (survivors)"] = event_block(use[use["disc"].notna()])
    by_group["no NAV (dead or unmatched funds)"] = event_block(use[use["disc"].isna()])

    profiles = {"all": profile(use, rel), "all, ex windows blanked": profile(use, rel_clean),
                "discount": profile(use[use["disc_grp"] == "discount"], rel), "premium": profile(use[use["disc_grp"] == "premium"], rel),
                "discount, ex windows blanked": profile(use[use["disc_grp"] == "discount"], rel_clean),
                "premium, ex windows blanked": profile(use[use["disc_grp"] == "premium"], rel_clean),
                "top flow third": profile(use[use["flow_grp"] == "top"], rel), "bottom flow third": profile(use[use["flow_grp"] == "bottom"], rel),
                "mid month": profile(use[~use["month_turn"]], rel), "month turn": profile(use[use["month_turn"]], rel)}

    vol = P["vol"].to_numpy()
    traded = np.array([np.mean(vol[use["iP"].to_numpy() + k, use["j"].to_numpy()] > 0) for k in EARN])
    in_count = inw.sum(axis=1)
    extra = {"panel_last_date": str(last), "counts": counts, "nav": nav_info,
             "events_eligible_and_known": int(len(use)), "events_eligible": int(ev["elig"].sum()),
             "events_per_year": float(len(use) / (n / 252)), "funds_with_an_event": int(use["permno"].nunique()),
             "funds_in_window_per_day": {"mean": float(in_count.mean()), "median": float(np.median(in_count)),
                                         "share_of_eligible_mean": float(np.mean(in_count[elig.sum(axis=1) > 0] / elig.sum(axis=1)[elig.sum(axis=1) > 0]))},
             "turnover_per_year": float(res_h["turn"]), "held_name_days_with_no_row": held_missing,
             "share_of_window_fund_days_with_volume": float(traded.mean()),
             "ex_to_pay_gap_sessions": {str(q): float(use["gap"].quantile(q)) for q in (0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99)},
             "share_of_events_at_month_turn": float(use["month_turn"].mean()),
             "events_with_a_nav": int(use["disc"].notna().sum()), "events_discount": int((use["disc_grp"] == "discount").sum()),
             "events_premium": int((use["disc_grp"] == "premium").sum()),
             "events_with_a_nav_by_era": {k[4:]: int(v["disc"].notna().sum()) for k, v in groups.items() if k.startswith("era=")},
             "participation_assumed": PARTICIPATION, "splits": splits, "per_event": by_group, "event_time_profile": profiles}
    res = explore.summarise(pnl, controls=ctl, extra=extra)
    explore.write(HERE, res, pnl, title=f"Long CEFs P-1..P+5 around the payment date, short the EW CEF market; shift(2), gross; to {last}", controls=ctl)
    use.drop(columns=["decl_missing"]).to_parquet(STAGE / "events_used.parquet")          # licensed rows: outside the repo

    f = lambda x, p=".2f": "n/a" if x is None else format(x, p)
    print("panel to", last, "|", counts, "| used", len(use), "| per year", round(extra["events_per_year"]), "| NAV", nav_info)
    print("funds in a window a day", extra["funds_in_window_per_day"], "| turnover/yr", round(res_h["turn"], 1), "| no-row", held_missing)
    print("ex-to-pay gap (sessions)", extra["ex_to_pay_gap_sessions"], "| month turn share", round(extra["share_of_events_at_month_turn"], 3))
    print(explore.table(res))
    for sname, sp in splits.items():
        print("\nSPLIT", sname)
        for bname, b in sp.items():
            s = b["full"]
            print(f"  {bname:38s} Sharpe {f(s['sharpe'])} t {f(s['t'])} ret {f(s['ann_ret'], '.2%')} vol {f(s['ann_vol'], '.2%')} from {s['first']} "
                  f"halves {f(b['early_half'])}/{f(b['late_half'])} eras " + " ".join(f"{k}:{f(v)}" for k, v in b["eras"].items()))
    print("\nPER EVENT (bp; fund less EW eligible universe)")
    for k, b in by_group.items():
        x = b["buy_and_hold_P-1_to_P+5"]
        if "mean_bp" not in x:
            print(f"  {k:34s} n {x['n']}"); continue
        g = lambda key: (f"{b[key]['mean_bp']:+.1f}({b[key]['t_clustered_by_month']:+.1f})" if "mean_bp" in b[key] else "n/a")
        print(f"  {k:34s} n {x['n']:6d} mean {x['mean_bp']:+6.1f} med {x['median_bp']:+6.1f} pos {x['share_positive']:.1%} t {x['t_clustered_by_month']:+5.2f} | mid {g('buy_and_hold_on_mid_quotes')} "
              f"exclean {g('buy_and_hold_ex_windows_blanked')} | P-1,P {g('P-1_and_P')} P+1..5 {g('P+1_to_P+5')} | plc-10 {g('placebo_window_at_P-10')} plc+10 {g('placebo_window_at_P+10')} "
              f"| adv ${b['median_adv_usd'] / 1e6:.2f}M px {b['median_price']:.1f} spr {b['median_spread_bp']:.0f}bp flow {b['median_flow_share_of_adv']:.2f}")
    print("\nPROFILE (bp, clustered t)")
    for k, pr in profiles.items():
        print(f"  {k:30s}", " ".join(f"{kk}:{v['mean_bp']:+.1f}({v['t_clustered_by_month']:+.1f})" if "mean_bp" in v else f"{kk}:n/a" for kk, v in pr.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
