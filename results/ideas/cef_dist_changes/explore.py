"""Explore: a closed-end fund cuts or raises its regular distribution. Read as a dated EVENT.

    QUANTT_ENV_FILE=<env file> python3 results/ideas/cef_dist_changes/explore.py

The desk killed distribution data twice, as a universe FILTER and inside the Kalman model
(docs/RESEARCH_STATE.md, "Distribution data"). It never read the change as an event. The
practitioner claim: income holders sell a fund that cuts, the price overshoots and recovers;
a raise is followed by slow drift up.

FIXED BEFORE ANY RETURN WAS READ (2026-11-16). Only counts had been read: 140,219 regular
ex-dates on 1,038 funds since 2000, declaration date missing on 0.6% (14.7% in 2000, 3.9% in
2001, under 0.5% after), 10,935 changes of 5% or more, 8,211 of them from a stable base.

  panel     every CRSP closed-end fund, dead ones included (~/quantt_research/crsp_cef_daily.parquet,
            staged by scripts/research/stage_crsp_cefs.py), CRSP total returns. No NAV is used.
  regular   crsp_a_stock.stkdistributions rows with distype 'CD' and disdetailtype 'CDIV'
            (ordinary cash dividend) and disfreqtype 'M' or 'Q'. LEFT OUT by code: 'SD'
            (special, disfreqtype 'E'), 'CG' (capital gain), 'ROC', 'CP', 'SP', 'FRS', and
            ordinary rows typed annual, semi-annual, year-end or unknown ('A','S','Y','U').
            Rows that share an ex-date are summed (39 ex-dates).
  event     a declaration whose regular amount differs from the fund's previous regular
            amount by 5% or more, where
              - the two previous amounts were within 5% of each other (a STABLE BASE: this
                removes the cut back from a year-end extra that CRSP typed as ordinary, and
                most funds that pay a different amount every period);
              - the frequency code is the same as the previous payment's and the previous
                ex-date is at most 45 days (monthly) or 135 days (quarterly) earlier;
              - no stock split or stock dividend ('FRS') went ex between the two;
              - the new amount is between 0.1 and 3 times the old;
              - CRSP has a declaration date and it is not after the ex-date;
              - it is the first ex-date carrying that declaration date (one announcement
                that sets three months is one event).
            RAISES with an ex-date from 1 December to 15 January are left out of the raise
            book: 865 of 3,397 stable-base raises have a December ex-date, which is year-end
            extras typed as ordinary, not a raised rate. Cuts need no such rule (stable base).
  timing    D0 = the first session on or after CRSP's declaration date. CRSP's date runs a
            median of one session late against the fund's own announcement, so the event
            is taken as known at the close of K = D0 + 1 session. Decide at K's close, fill
            at K+1's close, earn K+2 .. K+1+h (the desk's shift(2), on harness.evaluate).
            Asserted in code: K is strictly after the declaration date.
  eligible  price >= $2 and 21-session average dollar volume >= $500,000, both through K-1.
  books     (a) CUT: long the event funds equally, short the equal-weighted return of every
            eligible closed-end fund that day (the CEF market), for h = 20 and h = 60.
            (b) RAISE: the same, long. One unit long against one unit short. Flat on a day
            with fewer than 3 funds in a window.
            The announcement window (D0-1 .. K+1, four sessions ending at our fill) is
            reported separately. It cannot be traded.
  controls  1. UNCHANGED: the same funds' declarations where the amount changed by under
               0.5%, not within 60 sessions after one of that fund's own changes. Same
               position in the ex-date cycle as the events, no news.
            2. PEERS: CRSP has no fund category. Stand-in, said here so it is not mistaken
               for one: for each event the five eligible funds with the highest daily-return
               correlation over the 250 sessions ending K-6, of the same tax class (CRSP
               types a tax-exempt dividend distaxtype 'N', which marks a municipal fund),
               with no change of their own within 60 sessions either side.
            3. DROPPED AS MUCH: for each event the five eligible funds, with no change of
               their own within 60 sessions either side, whose return against the CEF
               market over the three sessions ending K is nearest the event fund's. If a
               cut fund only rebounds like any fund that fell as far, this scores the same.
  checks    named in advance: the fund's own ex-date cycle removed (its sessions X-3 .. X+3
            earn nothing); entry and exit on closing mid quotes; one more skipped session;
            the long leg alone and against PCEF (the tradable form); municipal against
            taxable; cut size 5-10%, 10-20%, over 20%; monthly against quarterly payers.
  per event buy-and-hold: the fund's compounded return over K+2 .. K+1+h less the CEF
            market's, with mean, median, share positive and a t clustered by month of K.
  expected  CUT: a fall of 1% to 3% against the market in the announcement window, then a
            positive 20-session return that is larger than each control's. RAISE: positive.
            If control 3 scores as well as the cuts, the idea is short-term reversal in a
            different coat and is not new.
Gross. No cost and no borrow is modelled; the closing bid-ask spread is reported beside it.
Licensed rows are written only under ~/quantt_research/cef_dist_changes/.
"""
# RESUMED RUN. The run of 2026-11-16 was cut off (the editor was force quit) after the docstring
# above and this script were written and before any return was read: no results.json existed,
# raw_dist.parquet was whole and quotes.parquet was a zero-byte file. Completed on 2026-11-18.
# The rule above is unchanged, word for word. One fix was made after the interruption, in
# stage(): a staged file that does not open as parquet is rebuilt, not trusted. The counts in
# the docstring were the first researcher's, read before the code was final; this code counts
# 10,987 changes of 5% or more and 8,003 from a stable base with an acceptable series (the
# docstring says 10,935 and 8,211). The run's own counts are in results.json and are the ones
# the card quotes. Checks made after the returns were read are in checks.py, labelled as such.
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
STAGE = Path.home() / "quantt_research" / "cef_dist_changes"
PANEL = Path.home() / "quantt_research" / "crsp_cef_daily.parquet"
MIN_PRICE, MIN_ADV, MIN_NAMES = 2.0, 500_000.0, 3
THRESH, UNCH, STABLE = 0.05, 0.005, 0.05
HOLDS = (20, 60)
BLOCK = 60
N_MATCH = 5
ERAS = explore.ERAS


# ---------------------------------------------------------------------------- staging
def stage() -> None:
    """Pull the two licensed extracts once. Read-only at R2; rows stay outside the repo."""
    if REPO.resolve() in STAGE.resolve().parents:
        raise SystemExit("licensed rows stay outside the repository")
    STAGE.mkdir(parents=True, exist_ok=True)
    raw, quotes = STAGE / "raw_dist.parquet", STAGE / "quotes.parquet"
    # FIX MADE AFTER THE INTERRUPTION (2026-11-18). The first run was killed while quotes.parquet
    # was being written and left a zero-byte file, which `exists()` accepted. A staged file must
    # open as parquet with rows, or it is removed and pulled again.
    import pyarrow.parquet as pq
    for f in (raw, quotes):
        if f.exists():
            try:
                ok = pq.ParquetFile(f).metadata.num_rows > 0
            except Exception:                              # truncated or empty: rebuilt below, said aloud
                ok = False
            if not ok:
                print(f"stage: {f.name} does not open as parquet with rows; rebuilding it")
                f.unlink()
    if raw.exists() and quotes.exists():
        return
    from src.data import r2
    con = r2.connect()
    cef = pd.read_parquet(PANEL, columns=["permno"]).drop_duplicates()
    con.register("cef", cef)
    if not raw.exists():
        con.execute(f"""copy (select d.* from read_parquet('{r2.r2_path("crsp_a_stock", "stkdistributions")}') d
                        join cef using (permno) where disexdt >= date '1999-01-01') to '{raw}' (format parquet)""")
    if not quotes.exists():
        con.execute(f"""copy (select permno, dlycaldt as date, cast(dlybid as double) as bid,
                               cast(dlyask as double) as ask, cast(dlyvol as double) as vol
                        from read_parquet('{r2.r2_path("crsp_a_stock", "dsf_v2")}') join cef using (permno)
                        where dlycaldt >= date '2000-01-01' and securitysubtype = 'CEF'
                          and conditionaltype = 'RW' and tradingstatusflg = 'A')
                        to '{quotes}' (format parquet, compression zstd)""")


def pcef() -> pd.Series:
    """PCEF total return from Yahoo, cached. The tradable stand-in for the CEF market."""
    f = STAGE / "pcef.parquet"
    if not f.exists():
        import yfinance as yf
        h = yf.download("PCEF", start="2010-01-01", auto_adjust=True, threads=False, progress=False)
        if h is None or len(h) < 1000:
            raise RuntimeError("PCEF: Yahoo returned no usable history")
        c = h["Close"]
        c = c.iloc[:, 0] if isinstance(c, pd.DataFrame) else c
        pd.DataFrame({"date": c.index.tz_localize(None), "adj_close": c.to_numpy()}).to_parquet(f)
    p = pd.read_parquet(f).set_index("date")["adj_close"]
    return p.pct_change().dropna()


# ---------------------------------------------------------------------------- events
def declarations() -> tuple[pd.DataFrame, dict]:
    """Every regular declaration with its change against the previous one, and the counts."""
    d = pd.read_parquet(STAGE / "raw_dist.parquet")
    for c in ("disexdt", "disdeclaredt"):
        d[c] = pd.to_datetime(d[c])
    d["amt"] = d["disdivamt"].astype(float)
    reg = d[(d.distype == "CD") & (d.disdetailtype == "CDIV") & d.disfreqtype.isin(["M", "Q"]) & (d.amt > 0)]
    g = (reg.groupby(["permno", "disexdt"])
         .agg(amt=("amt", "sum"), decl=("disdeclaredt", "min"), freq=("disfreqtype", "first"),
              nfreq=("disfreqtype", "nunique"), muni_row=("distaxtype", lambda s: (s == "N").mean()))
         .reset_index().sort_values(["permno", "disexdt"]))
    muni = g.groupby("permno").muni_row.mean() > 0.5
    by = g.groupby("permno")
    g["prev"], g["prev2"] = by.amt.shift(1), by.amt.shift(2)
    g["prev_ex"], g["prev_freq"] = by.disexdt.shift(1), by.freq.shift(1)
    g["chg"] = g.amt / g.prev - 1
    g["gap"] = (g.disexdt - g.prev_ex).dt.days
    spl = d[d.distype == "FRS"][["permno", "disexdt"]]
    g["split"] = False
    for p, x in spl.itertuples(index=False):
        g.loc[(g.permno == p) & (g.prev_ex < x) & (g.disexdt >= x), "split"] = True
    g["first_of_decl"] = ~g.duplicated(["permno", "decl"]) | g.decl.isna()
    g["muni"] = g.permno.map(muni)
    g = g[g.disexdt >= "2000-01-01"]
    big = g.chg.abs() >= THRESH
    ok_series = (g.nfreq == 1) & (g.freq == g.prev_freq) & (g.gap <= np.where(g.freq == "M", 45, 135)) & ~g.split
    stable = (g.prev / g.prev2 - 1).abs() < STABLE
    ratio_ok = (g.amt / g.prev).between(0.1, 3.0)
    has_decl = g.decl.notna() & (g.decl <= g.disexdt)
    counts = {"regular_ex_dates": int(len(g)), "funds": int(g.permno.nunique()),
              "declaration_missing_share": float(g.decl.isna().mean()),
              "declaration_missing_share_by_year": {int(k): float(v) for k, v in g.groupby(g.disexdt.dt.year).decl.apply(lambda s: s.isna().mean()).items()},
              "declaration_after_ex_date": int((g.decl > g.disexdt).sum()),
              "changes_5pct": int(big.sum()), "of_which_series_ok": int((big & ok_series).sum()),
              "and_stable_base": int((big & ok_series & stable).sum()),
              "and_ratio_ok": int((big & ok_series & stable & ratio_ok).sum()),
              "and_declared": int((big & ok_series & stable & ratio_ok & has_decl).sum()),
              "and_first_of_declaration": int((big & ok_series & stable & ratio_ok & has_decl & g.first_of_decl).sum()),
              "changes_5pct_no_declaration_date": int((big & ok_series & stable & ratio_ok & g.decl.isna()).sum())}
    g["event"] = big & ok_series & stable & ratio_ok & has_decl & g.first_of_decl
    g["unchanged"] = (g.chg.abs() < UNCH) & ok_series & has_decl & g.first_of_decl
    g["any_change"] = big & has_decl                       # for blocking controls: every 5% change, stable base or not
    return g, counts


def cluster_t(x: pd.Series, cl: pd.Series) -> float:
    """t of the mean with standard errors clustered on `cl` (month of the decision)."""
    x = x.dropna()
    if len(x) < 10:
        return float("nan")
    e = x - x.mean()
    s = e.groupby(cl.reindex(x.index)).sum()
    se = np.sqrt((s ** 2).sum()) / len(x)
    return float(x.mean() / se)


def ev_row(x: pd.Series, cl: pd.Series) -> dict:
    x = x.dropna()
    return {"n": int(len(x)), "mean_bp": float(x.mean() * 1e4), "median_bp": float(x.median() * 1e4),
            "share_positive": float((x > 0).mean()), "t_clustered_by_month": cluster_t(x, cl)}


def main() -> int:
    stage()
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    last = df["date"].max().date()
    ret = df.pivot(index="date", columns="permno", values="ret")
    prc = df.pivot(index="date", columns="permno", values="prc")
    dv = df.pivot(index="date", columns="permno", values="dollar_volume")
    exd = df.pivot(index="date", columns="permno", values="div").fillna(0.0) > 0
    q = pd.read_parquet(STAGE / "quotes.parquet")
    q["date"] = pd.to_datetime(q["date"])
    bid = q.pivot(index="date", columns="permno", values="bid").reindex(index=ret.index, columns=ret.columns)
    ask = q.pivot(index="date", columns="permno", values="ask").reindex(index=ret.index, columns=ret.columns)
    vol = q.pivot(index="date", columns="permno", values="vol").reindex(index=ret.index, columns=ret.columns)
    good_q = (bid > 0) & (ask >= bid)
    mid = ((bid + ask) / 2).where(good_q)
    spread = ((ask - bid) / mid).where(good_q)
    idx, cols = ret.index, ret.columns
    T = len(idx)
    adv = dv.rolling(21, min_periods=10).mean()
    # ALIGNMENT. elig.loc[s] uses price and volume through s-1 only.
    elig = ((prc >= MIN_PRICE) & (adv >= MIN_ADV)).shift(1, fill_value=False)
    R = ret.fillna(0.0)                       # no row = the fund has stopped trading; the delisting return is on its last row
    mkt = ret.where(elig).mean(axis=1).fillna(0.0)
    rel = ret.sub(mkt, axis=0)
    Rn, mk, eln = R.to_numpy(), mkt.to_numpy(), elig.to_numpy()
    reln = rel.to_numpy()
    col_of = {p: j for j, p in enumerate(cols)}

    g, counts = declarations()
    g = g[g.permno.isin(cols)].copy()
    # D0 = first session on or after the declaration date; K = D0 + 1 session.
    has = g.decl.notna()
    d0 = np.full(len(g), -1)
    d0[has.to_numpy()] = idx.searchsorted(g.decl[has].to_numpy(), side="left")
    g["d0"], g["k"] = d0, d0 + 1
    g["j"] = g.permno.map(col_of)
    g = g[has & (g.k + 2 < T) & (g.d0 >= 30)].copy()
    assert (idx[g.k.to_numpy()] > g.decl.to_numpy()).all(), "lookahead: K is not after the declaration date"
    g["elig"] = eln[g.k.to_numpy(), g.j.to_numpy()] & ret.notna().to_numpy()[g.k.to_numpy(), g.j.to_numpy()]
    g["kdate"] = idx[g.k.to_numpy()]
    g["ymonth"] = g.kdate.dt.to_period("M").astype(str)
    dec_dj = (g.disexdt.dt.month == 12) | ((g.disexdt.dt.month == 1) & (g.disexdt.dt.day <= 15))
    g["cut"] = g.event & (g.chg < 0)
    g["raise_all"] = g.event & (g.chg > 0)
    g["raise"] = g.raise_all & ~dec_dj
    counts.update({"cuts_declared_in_panel": int(g.cut.sum()), "raises_declared_in_panel": int(g.raise_all.sum()),
                   "raises_after_year_end_rule": int(g["raise"].sum()),
                   "cuts_eligible": int((g.cut & g.elig).sum()), "raises_eligible": int((g["raise"] & g.elig).sum())})

    # blocks: a fund-session within BLOCK sessions either side of any 5% change of its own
    chg_flag = np.zeros((T, len(cols)), bool)
    a = g[g.any_change]
    chg_flag[a.k.to_numpy(), a.j.to_numpy()] = True
    cf = pd.DataFrame(chg_flag, index=idx, columns=cols)
    after = cf.rolling(BLOCK + 1, min_periods=1).max().astype(bool)             # a change in the last 60 sessions
    blocked = (after | cf[::-1].rolling(BLOCK + 1, min_periods=1).max()[::-1].astype(bool)).to_numpy()
    after_prev = after.shift(1, fill_value=False).to_numpy()
    g["unch_ctrl"] = g.unchanged & ~after_prev[g.k.to_numpy(), g.j.to_numpy()]
    muni_col = np.array([bool(g.groupby("permno").muni.first().get(p, False)) for p in cols])
    rel3 = rel.fillna(0.0).rolling(3).sum().to_numpy()                          # sessions K-2 .. K

    def window(k: np.ndarray, j: np.ndarray, h: int, skip: int = 0) -> np.ndarray:
        """Bool matrix of EARNING sessions K+2+skip .. K+1+skip+h for each (K, fund)."""
        w = np.zeros((T, len(cols)), bool)
        for kk, jj in zip(k, j):
            w[kk + 2 + skip: min(kk + 2 + skip + h, T), jj] = True
        return w

    def run_book(w: np.ndarray, hedge: str = "cef") -> tuple[pd.Series, dict]:
        """Long the window funds equally; short the CEF market (every eligible fund equally)."""
        n = w.sum(axis=1)
        on = n >= MIN_NAMES
        L = np.where(on[:, None], w / np.where(n > 0, n, 1)[:, None], 0.0)
        if hedge == "cef":
            ne = eln.sum(axis=1)
            S = np.where((on & (ne > 0))[:, None], eln / np.where(ne > 0, ne, 1)[:, None], 0.0)
            L = np.where((ne > 0)[:, None], L, 0.0)
        else:
            S = 0.0
        earn = pd.DataFrame(L - S, index=idx, columns=cols)
        H = earn.shift(-harness.EXEC_LAG).fillna(0.0)
        res = harness.evaluate(H, R)
        Hl = pd.DataFrame(L, index=idx, columns=cols).shift(-harness.EXEC_LAG).fillna(0.0)
        info = {"turnover_per_year_long_leg": float(harness.evaluate(Hl, R)["turn"]),
                "names_long_mean": float(n[on].mean()) if on.any() else 0.0, "share_days_on": float(on.mean())}
        return res["pnl"], info

    def bhar(k: np.ndarray, j: np.ndarray, h: int, skip: int = 0, drop: np.ndarray | None = None) -> np.ndarray:
        """Fund's compounded return over K+2+skip .. K+1+skip+h less the CEF market's. NaN if the window runs off the panel."""
        out = np.full(len(k), np.nan)
        for i, (kk, jj) in enumerate(zip(k, j)):
            a0, a1 = kk + 2 + skip, kk + 2 + skip + h
            if a1 > T:
                continue
            f, m = Rn[a0:a1, jj], mk[a0:a1]
            if drop is not None:
                keep = ~drop[a0:a1, jj]
                f, m = f[keep], m[keep]
            out[i] = np.prod(1 + f) - np.prod(1 + m)
        return out

    def matches(ev: pd.DataFrame, how: str) -> pd.DataFrame:
        """Five matched non-event funds per event, as pseudo-events at the same K."""
        rows = []
        raw = ret.to_numpy()
        for e_i, (kk, jj) in enumerate(zip(ev.k.to_numpy(), ev.j.to_numpy())):
            cand = eln[kk] & ~blocked[kk] & ~np.isnan(raw[kk])
            cand[jj] = False
            if how == "peers":
                cand &= muni_col == muni_col[jj]
                a0, a1 = max(kk - 255, 0), kk - 5                      # 250 sessions ending K-6
                X = raw[a0:a1]
                x = X[:, jj]
                okc = cand & (np.isfinite(X).sum(axis=0) >= 120)
                if np.isfinite(x).sum() < 120 or okc.sum() < N_MATCH:
                    continue
                cc = np.where(okc)[0]
                sub = pd.DataFrame(X[:, cc])
                c = sub.corrwith(pd.Series(x)).to_numpy()
                pick = cc[np.argsort(-np.nan_to_num(c, nan=-2))[:N_MATCH]]
            else:
                if cand.sum() < N_MATCH:
                    continue
                cc = np.where(cand)[0]
                pick = cc[np.argsort(np.abs(rel3[kk, cc] - rel3[kk, jj]))[:N_MATCH]]
            rows += [(e_i, kk, p) for p in pick]
        return pd.DataFrame(rows, columns=["event", "k", "j"])

    exwin = np.zeros((T, len(cols)), bool)                  # the fund's own X-3 .. X+3
    exn = exd.to_numpy()
    for s in range(-3, 4):
        exwin |= np.roll(exn, s, axis=0) if s == 0 else (np.vstack([np.zeros((s, len(cols)), bool), exn[:-s]]) if s > 0
                                                         else np.vstack([exn[-s:], np.zeros((-s, len(cols)), bool)]))
    pc = pcef().reindex(idx)

    out = {"panel_last_date": str(last), "counts": counts, "pcef_last_date": str(pc.dropna().index.max().date())}
    years = (idx[-1] - idx[30]).days / 365.25
    pnl_keep = {}
    for name in ("cut", "raise"):
        ev = g[g[name] & g.elig].reset_index(drop=True)
        k, j = ev.k.to_numpy(), ev.j.to_numpy()
        cl = ev.ymonth
        sec = {"events": int(len(ev)), "events_per_year": float(len(ev) / years), "funds": int(ev.permno.nunique()),
               "events_by_year": {int(a): int(b) for a, b in ev.kdate.dt.year.value_counts().sort_index().items()},
               "median_change": float(ev.chg.median()),
               "days_declared_to_ex_median": float((ev.disexdt - ev.decl).dt.days.median()),
               "share_muni": float(ev.muni.mean()), "share_monthly": float((ev.freq == "M").mean())}
        # liquidity and spread at K
        kd = idx[k]
        sec["liquidity_at_decision"] = {
            "median_adv21_usd": float(np.nanmedian(adv.to_numpy()[k - 1, j])), "p10_adv21_usd": float(np.nanpercentile(adv.to_numpy()[k - 1, j], 10)),
            "median_price": float(np.nanmedian(prc.to_numpy()[k, j])), "median_cap_usd_m": float(np.nanmedian(df.pivot(index="date", columns="permno", values="cap").to_numpy()[k, j]) / 1e3),
            "spread_bp_median": float(np.nanmedian(spread.to_numpy()[k, j]) * 1e4), "spread_bp_mean": float(np.nanmean(spread.to_numpy()[k, j]) * 1e4),
            "spread_bp_p90": float(np.nanpercentile(spread.to_numpy()[k, j], 90) * 1e4),
            "share_with_quote": float(np.isfinite(spread.to_numpy()[k, j]).mean()),
            "share_zero_volume_at_K": float((vol.to_numpy()[k, j] == 0).mean()),
            "share_zero_volume_at_fill_K+1": float((vol.to_numpy()[k + 1, j] == 0).mean())}
        # event-time profile, fund less market, relative to K (K = D0+1)
        prof = {}
        for s in list(range(-11, 3)) + [5, 10, 20, 40, 60]:
            pass
        cum = {}
        for lab, a0, a1 in (("pre K-21..K-3 (before the announcement window)", -21, -3), ("announcement D0-1..K+1 (not tradable)", -2, 1),
                            ("K+2..K+6", 2, 6), ("K+7..K+21", 7, 21), ("K+22..K+61", 22, 61)):
            v = []
            for kk, jj in zip(k, j):
                if kk + a0 < 0 or kk + a1 >= T:
                    v.append(np.nan); continue
                v.append(np.prod(1 + Rn[kk + a0: kk + a1 + 1, jj]) - np.prod(1 + mk[kk + a0: kk + a1 + 1]))
            cum[lab] = ev_row(pd.Series(v), cl)
        sec["event_time_fund_less_market"] = cum
        daily = {}
        for s in range(-6, 8):
            ok = (k + s >= 0) & (k + s < T)
            v = pd.Series(np.where(ok, reln[np.clip(k + s, 0, T - 1), j], np.nan))
            daily[f"K{s:+d}"] = {"mean_bp": float(v.mean() * 1e4), "t": cluster_t(v, cl)}
        sec["daily_profile_fund_less_market"] = daily

        ctrl_sets = {
            "unchanged declarations, same funds": g[g.unch_ctrl & g.elig & g.permno.isin(ev.permno.unique())][["k", "j", "ymonth"]].reset_index(drop=True),
        }
        mp, mr = matches(ev, "peers"), matches(ev, "drop")
        for lab, m in (("correlation-matched peers", mp), ("dropped as much", mr)):
            m = m.copy(); m["ymonth"] = ev.ymonth.to_numpy()[m.event.to_numpy()]
            ctrl_sets[lab] = m
        sec["controls_n"] = {a: int(len(b)) for a, b in ctrl_sets.items()}
        sec["matched_rel3_bp"] = {"events": float(np.nanmean(rel3[k, j]) * 1e4),
                                  "dropped as much": float(np.nanmean(rel3[mr.k.to_numpy(), mr.j.to_numpy()]) * 1e4),
                                  "peers": float(np.nanmean(rel3[mp.k.to_numpy(), mp.j.to_numpy()]) * 1e4)}
        for h in HOLDS:
            key = f"{name}_{h}"
            pnl, info = run_book(window(k, j, h))
            pnl = pnl.iloc[30:-harness.EXEC_LAG]
            controls, cinfo = {}, {}
            for lab, m in ctrl_sets.items():
                cp, ci = run_book(window(m.k.to_numpy(), m.j.to_numpy(), h))
                controls[lab] = cp.reindex(pnl.index)
                controls[f"event book less: {lab}"] = pnl - cp.reindex(pnl.index)
            lo, linfo = run_book(window(k, j, h), hedge="none")
            lo = lo.reindex(pnl.index)
            wdrop = window(k, j, h) & ~exwin
            nx, _ = run_book(wdrop)
            sk, _ = run_book(window(k, j, h, skip=1))
            controls["check: own ex-date cycle (X-3..X+3) earns nothing"] = nx.reindex(pnl.index)
            controls["check: one more skipped session"] = sk.reindex(pnl.index)
            controls["form: long leg alone, no hedge"] = lo
            res = explore.summarise(pnl, controls=controls, extra=info)
            # the tradable form against PCEF, on PCEF's own dates
            on = (lo != 0) & pc.reindex(pnl.index).notna()
            vs = (lo - pc.reindex(pnl.index).where(lo != 0, 0.0)).loc[pc.dropna().index.min():]
            vs = vs[vs.index.isin(pc.dropna().index)]
            res["form_long_against_PCEF"] = explore.summarise(vs)
            # per-event buy and hold
            b = pd.Series(bhar(k, j, h))
            pe = {"events": ev_row(b, cl)}
            for a, bq in ERAS:
                msk = (ev.kdate >= a) & (ev.kdate <= bq)
                pe[f"events {a[:4]}-{min(int(bq[:4]), 2025)}"] = ev_row(b[msk.to_numpy()], cl)
            half = ev.kdate.sort_values().iloc[len(ev) // 2]
            pe["events early half"] = ev_row(b[(ev.kdate <= half).to_numpy()], cl)
            pe["events late half"] = ev_row(b[(ev.kdate > half).to_numpy()], cl)
            for lab, m in ctrl_sets.items():
                cb = pd.Series(bhar(m.k.to_numpy(), m.j.to_numpy(), h))
                pe[lab] = ev_row(cb, m.ymonth)
                if "event" in m:
                    paired = b - cb.groupby(m.event.to_numpy()).mean().reindex(range(len(ev)))
                    pe[f"event less its own: {lab}"] = ev_row(paired, cl)
            pe["check: own ex-date cycle removed"] = ev_row(pd.Series(bhar(k, j, h, drop=exwin)), cl)
            pe["check: one more skipped session"] = ev_row(pd.Series(bhar(k, j, h, skip=1)), cl)
            # mid quotes: enter at K+1's mid, leave at K+1+h's mid
            pn, mn = prc.to_numpy(), mid.to_numpy()
            okm = (k + 1 + h < T)
            adj = np.full(len(k), np.nan)
            adj[okm] = (mn[k[okm] + 1 + h, j[okm]] / pn[k[okm] + 1 + h, j[okm]]) / (mn[k[okm] + 1, j[okm]] / pn[k[okm] + 1, j[okm]])
            raw_f = np.array([np.prod(1 + Rn[kk + 2: kk + 2 + h, jj]) if kk + 2 + h <= T else np.nan for kk, jj in zip(k, j)])
            raw_m = np.array([np.prod(1 + mk[kk + 2: kk + 2 + h]) if kk + 2 + h <= T else np.nan for kk in k])
            both = pd.Series(raw_f * adj - raw_m)
            pe["check: entry and exit on closing mid quotes"] = ev_row(both, cl)
            pe["same events on closes (those with both quotes)"] = ev_row(b.where(both.notna()), cl)
            pe["raw fund return, no hedge"] = ev_row(pd.Series(raw_f - 1), cl)
            for lab, msk in (("municipal", ev.muni), ("taxable", ~ev.muni.astype(bool)), ("monthly payers", ev.freq == "M"), ("quarterly payers", ev.freq == "Q"),
                             ("change 5-10%", ev.chg.abs() < 0.10), ("change 10-20%", (ev.chg.abs() >= 0.10) & (ev.chg.abs() < 0.20)), ("change over 20%", ev.chg.abs() >= 0.20),
                             ("ADV $0.5-2M", pd.Series(adv.to_numpy()[k - 1, j] < 2e6)), ("ADV over $2M", pd.Series(adv.to_numpy()[k - 1, j] >= 2e6))):
                pe[f"split: {lab}"] = ev_row(b[np.asarray(msk, bool)], cl)
            res["per_event_buy_and_hold_less_market"] = pe
            sec[key] = res
            pnl_keep[key] = (pnl, controls)
            print(f"\n== {key}: {len(ev)} events, {sec['events_per_year']:.0f} a year; long names {info['names_long_mean']:.1f}; on {info['share_days_on']:.0%} of days; long-leg turnover {info['turnover_per_year_long_leg']:.1f}/yr")
            print(explore.table(res))
            print("against PCEF:", {a: round(res["form_long_against_PCEF"]["full"][a], 3) for a in ("sharpe", "t", "ann_ret", "ann_vol")}, res["form_long_against_PCEF"]["full"]["first"])
            for a, v in pe.items():
                print(f"  {a:55s} n {v['n']:6d} mean {v['mean_bp']:+7.1f}bp median {v['median_bp']:+7.1f}bp pos {v['share_positive']:.1%} t {v['t_clustered_by_month']:+.2f}")
        print(f"\n{name}: liquidity", json.dumps(sec["liquidity_at_decision"]))
        for a, v in cum.items():
            print(f"  {a:50s} n {v['n']:6d} mean {v['mean_bp']:+7.1f}bp median {v['median_bp']:+7.1f}bp pos {v['share_positive']:.1%} t {v['t_clustered_by_month']:+.2f}")
        print("  " + " ".join(f"{a}:{v['mean_bp']:+.0f}({v['t']:+.1f})" for a, v in daily.items()))
        print("  rel3 at K, bp:", sec["matched_rel3_bp"], "| controls n", sec["controls_n"])
        out[name] = sec
    print(json.dumps(counts, indent=1))
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, name in zip(axes, ("cut", "raise")):
        for h in HOLDS:
            pnl, controls = pnl_keep[f"{name}_{h}"]
            (pnl.cumsum() * 100).plot(ax=ax, label=f"{name}, {h} sessions")
            (controls["dropped as much"].fillna(0).cumsum() * 100).plot(ax=ax, alpha=0.6, ls="--", label=f"control: dropped as much, {h}")
        ax.set_title(f"{name}: long event funds, short the CEF market; shift(2), gross; to {last}", fontsize=9)
        ax.set_ylabel("cumulative return, % (not compounded)"); ax.grid(alpha=0.3); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(HERE / "equity.png", dpi=110); plt.close(fig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
