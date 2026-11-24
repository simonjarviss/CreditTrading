#!/usr/bin/env python3
"""Build data/etf_daily.parquet: daily TOTAL RETURN panel for the 9 credit/rates ETFs.

Columns: [date, ticker, permno, ret_total, ret_px, prc_adj, volume, source].

CRSP leg (inception .. 2024-12-31): R2 wrds/crsp_a_stock/dsf.parquet.
  The R2 manifest (wrds/manifest.json) describes per-year source partitions
  crsp.dsf/2000..2025, but the physical mirror stores one combined
  dsf.parquet — glob-verified: no per-year objects exist in the bucket.
  2004-05 coverage was verified inside the combined file (504 trading days
  for the 2002-inception funds). The 2025 partition has 0 rows, hence the
  yfinance splice.
  - ret  = CRSP daily total return (distributions reinvested on ex-date).
  - retx = price-only return.
  - prc < 0 means CRSP recorded a bid/ask midpoint instead of a trade price
    (happens on zero-trade days: 30 ANGL rows, 38 FALN, 1 JNK) -> abs().
  - prc_adj = abs(prc)/cfacpr puts prices on the current share basis across
    the two real reverse splits in the panel: BIL 1:2 effective 2017-11-30
    (cfacpr 0.5 -> 1.0) and JNK 1:3 effective 2019-05-06 (1/3 -> 1.0).
  - ret is NULL only on each fund's inception day (asserted); those rows are
    dropped so ret_total is never NaN.

yfinance leg (2025-01-01 .. present): one download with auto_adjust=False +
actions=True, which returns raw Close, Adj Close, Dividends and Capital
Gains together (Adj Close here is numerically what auto_adjust=True would
put in Close). Two total-return candidates are computed:
  - adjclose: Adj Close pct_change (the spec's default), and
  - inhouse:  (Close + Div + CapGains) / prev Close - 1.
The 2024 overlap validation against CRSP ret picks, per ticker, the method
that passes max|diff| < 5 bp; if adjclose fails on dividend ex-dates
(yfinance back-propagates a rounded adjustment factor — see
archive/calendar-premia-v2/scripts/build_etf.py header) the inhouse TR is
used and the diagnostics are printed either way, never silently accepted.

Splice: yfinance rows strictly after each ticker's CRSP end date; the
yfinance bar immediately preceding the first spliced bar must BE the CRSP
end date (holiday-aware seam check), so the first spliced return accrues
exactly from the CRSP end close.

Bad-print repair (explicit, loud, table-driven): CRSP records the last
trade, and on 2013-08-02 ANGL's closing print was a stub-quote trade at
40.35 (closing bid 27.64, intraday askhi 40.35, 5,100 shares, NAV ~27.1)
producing a fake +48.9% / -32.5% two-day swing that fully reverses.
Yahoo's official consolidated close that day is 27.35 (within the day's
27.12-27.50 real range). BAD_PRINTS replaces the print with the Yahoo
close fetched at build time and recomputes the two affected returns,
preserving CRSP's dividend component (ret - retx). The 2008-10 HYG/JNK
+/-11-15% days are genuine crisis prints (300k-500k shares) and are kept.
A reversal scan prints any other |ret|>8% low-volume reversal candidates
for manual review; only rows in BAD_PRINTS are ever altered.

RESTORED 2026-10-11 (RESEARCH_PLAN_2026-10-09 item 0.1) from tag
`pre-clean-slate`; `data/etf_daily.parquet` (read by src/backtest/engine.py and
ops/common.py's replay) had no fetcher. Changes, nothing else:

  * THREE SOURCES BY DATE: CRSP through 2024-12-31 (unchanged), yfinance from
    2025-01-02 through `YF_LAST` (2026-07-20, the old panel's last date;
    unchanged), and Alpaca daily bars after it, `source == "alpaca"`
    (`scripts/rv/alpaca_daily.py`: SIP, raw prices, cash dividends from Alpaca
    corporate actions, ret_total in-house = (close + div)/prev close - 1,
    prc_adj = the raw close, which is on the current share basis because the
    module raises on any split since 2023-12-15). Before the splice the Alpaca
    leg must pass the SAME gate the yfinance leg passes against CRSP on 2024
    (max |diff| < SPLICE_MAX_BP per ticker, ex-dates identical) and agree with
    yfinance on 2025-01-02..yesterday under that gate.
  * EFA, EEM, GLD, DBC added. PERMNOs from `crsp_a_stock.stocknames` on the
    R2 mirror, 2026-10-11, by ticker with the name record covering 2024-12-31:
    EFA 89129 "ISHARES TRUST", EEM 89730 "ISHARES TRUST", GLD 90448 "SPDR GOLD
    TRUST", DBC 91129 "INVESCO D B COMM IDX TRK FD" (all shrcd 73). The
    ranges and row counts in PERMNOS were read from `dsf` the same day.
  * The `< 15%` daily-return sanity bound was written for nine credit and
    rates ETFs. Equity ETFs breach it on genuine days, so rows at or above 15%
    must now be NAMED in `LARGE_MOVES` with their evidence; any other raises,
    and a named row that is missing raises too (the mirror changed).
  * `--out` (default data/etf_daily.parquet), so a rebuild can be staged and
    proved byte-identical (`scripts/rv/panel_identity.py`) first.

XASSET MODE, added 2026-10-14 (gate DG1 of
results/xasset/PREREG_XASSET_SLATE_2026-10-12.md, revision 3, approved):

  * `--xasset --out PATH` builds the 13 tickers above PLUS the nine slate names
    the panel lacked, `XASSET_PERMNOS` (SPY, EMB, PFF, MUB, BKLN, CWB, IEI,
    TLH, AGG; share code 73; permno, range and row count read from `dsf` on
    the R2 mirror by `scripts/xasset/slate_feasibility.py --crsp`, 2026-10-12,
    results/xasset/feasibility/slate_feasibility_2026-10-12.csv), through the SAME gates.
  * It adds ONE column, `prc_signed`: CRSP `dsf.prc` exactly as recorded,
    unadjusted and SIGNED. CRSP stores minus the bid/ask midpoint when no
    trade closed the session, so `prc_signed < 0` is the no-closing-trade
    flag (the slate's quality check Q4). It is NaN outside the CRSP leg,
    where no CRSP record exists, by construction rather than as a fill. The
    BAD_PRINTS repair changes `prc_adj`, never `prc_signed`, which keeps
    what CRSP recorded.
  * `prc_adj` stays |prc|/cfacpr. The new column and the nine names NEVER
    reach data/etf_daily.parquet, which src/backtest/engine.py and
    ops/common.py's replay read: `--xasset` refuses any `--out` under data/.
  * Without `--xasset` the build is unchanged: the same 13 tickers, the same
    eight columns, the same gates.
  * The nine names' own >= 15% days are named in `XASSET_LARGE_MOVES`, with
    the same evidence rule as `LARGE_MOVES`; they are checked only in this mode.

Run:  python3 scripts/build_etf_daily.py [--out PATH]
      python3 scripts/build_etf_daily.py --xasset --out results/xasset/_cache_xasset/etf_daily_xasset.parquet
"""

import argparse
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.data.r2 import connect, r2_path, q  # noqa: E402

OUT = REPO / "data" / "etf_daily.parquet"
YF_START = "2023-12-15"  # buffer: every 2024 overlap return must be computable
SPLICE_MAX_BP = 5.0      # acceptance gate on the 2024 overlap, per ticker
# yfinance through this date (the old panel's last date), Alpaca after it.
YF_LAST = "2026-07-20"
ALPACA_CHECK_FROM = "2025-01-02"   # Alpaca vs yfinance from here to yesterday

# Resolved ticker -> permno map (built/verified by scripts/build_permno_map.py;
# expected dsf ranges/rowcounts re-asserted here so a mirror change is loud).
PERMNOS = {
    "HYG":  {"permno": 91933, "first": "2007-04-11", "last": "2024-12-31", "n": 4463},
    "JNK":  {"permno": 92922, "first": "2007-12-04", "last": "2024-12-31", "n": 4298},
    "ANGL": {"permno": 13348, "first": "2012-04-11", "last": "2024-12-31", "n": 3202},
    "FALN": {"permno": 16094, "first": "2016-06-16", "last": "2024-12-31", "n": 2150},
    "SHY":  {"permno": 89470, "first": "2002-07-26", "last": "2024-12-31", "n": 5647},
    "BIL":  {"permno": 92027, "first": "2007-05-30", "last": "2024-12-31", "n": 4429},
    "IEF":  {"permno": 89469, "first": "2002-07-26", "last": "2024-12-31", "n": 5647},
    "LQD":  {"permno": 89467, "first": "2002-07-26", "last": "2024-12-31", "n": 5647},
    "TLT":  {"permno": 89468, "first": "2002-07-26", "last": "2024-12-31", "n": 5647},
    # added 2026-10-11 (plan item 0.1); permno, range and n read from the mirror that day
    "EFA":  {"permno": 89129, "first": "2001-08-17", "last": "2024-12-31", "n": 5879},
    "EEM":  {"permno": 89730, "first": "2003-04-11", "last": "2024-12-31", "n": 5468},
    "GLD":  {"permno": 90448, "first": "2004-11-18", "last": "2024-12-31", "n": 5063},
    "DBC":  {"permno": 91129, "first": "2006-02-03", "last": "2024-12-31", "n": 4759},
}
TICKERS = list(PERMNOS)
BY_PERMNO = {v["permno"]: t for t, v in PERMNOS.items()}

# XASSET gate DG1 (2026-10-14): the nine slate names the panel lacked. Permno,
# range and n from `dsf` on the R2 mirror, 2026-10-12
# (results/xasset/feasibility/slate_feasibility_2026-10-12.csv, columns crsp_permno,
# crsp_first, crsp_last, crsp_rows). Used only under --xasset.
XASSET_PERMNOS = {
    "SPY":  {"permno": 84398, "first": "1993-01-29", "last": "2024-12-31", "n": 8038},
    "EMB":  {"permno": 92491, "first": "2007-12-19", "last": "2024-12-31", "n": 4287},
    "PFF":  {"permno": 91874, "first": "2007-03-30", "last": "2024-12-31", "n": 4470},
    "MUB":  {"permno": 92273, "first": "2007-09-10", "last": "2024-12-31", "n": 4358},
    "BKLN": {"permno": 12631, "first": "2011-03-03", "last": "2024-12-31", "n": 3481},
    "CWB":  {"permno": 92914, "first": "2009-04-16", "last": "2024-12-31", "n": 3955},
    "IEI":  {"permno": 91705, "first": "2007-01-11", "last": "2024-12-31", "n": 4524},
    "TLH":  {"permno": 91704, "first": "2007-01-11", "last": "2024-12-31", "n": 4524},
    "AGG":  {"permno": 89848, "first": "2003-09-26", "last": "2024-12-31", "n": 5352},
}
assert not set(XASSET_PERMNOS) & set(PERMNOS)

# Known bad closing prints, repaired with Yahoo's official consolidated close
# (fetched at build time, sanity-bounded). Evidence in the module docstring.
BAD_PRINTS = {("ANGL", "2013-08-02"): "stub-quote close 40.35 vs bid 27.64, NAV ~27.1"}

# Genuine daily moves of 15% or more, by name. Each was checked 2026-10-11
# against a second source (yfinance history, auto_adjust=False, gives the
# same return to the printed precision) and trades on very large volume, so
# none is a stub print. Global equity markets on 2008-10-13 had their largest
# up-day of the crisis; EFA and EEM moved together.
LARGE_MOVES = {
    ("EFA", "2008-10-13"): "CRSP ret +15.89%, vol 57.8m; yfinance +15.89%",
    ("EEM", "2008-10-13"): "CRSP ret +22.77%, vol 177.2m; yfinance +22.77%",
    ("EEM", "2008-10-15"): "CRSP ret -16.17%, vol 153.7m; yfinance -16.17%",
    ("EEM", "2008-10-28"): "CRSP ret +20.93%, vol 219.3m; yfinance +20.93%",
}
LARGE_MOVE_BOUND = 0.15
# The nine XASSET names' own >= 15% days (checked only under --xasset, so the
# default build's "named row missing" check is unaffected). Named 2026-10-14 by
# the same rule as LARGE_MOVES: the first --xasset build raised on exactly these
# three, each was checked against yfinance history (auto_adjust=False; Adj Close
# pct_change and (Close + Dividends)/prev Close both give the same return to the
# printed precision), each trades on volume well above the preceding sessions,
# and none reverses the next session (+8.5%, +3.5%, +8.3%), so none is a stub
# print. No value is altered: naming a row only stops the gate raising on it.
XASSET_LARGE_MOVES = {
    ("PFF", "2008-10-13"): "CRSP ret +19.22%, vol 1.13m (0.93m prior day); yfinance +19.22%; next day +8.50%",
    ("PFF", "2009-03-10"): "CRSP ret +16.42%, vol 2.23m (1.37m prior day); yfinance +16.42%; next day +3.50%",
    ("PFF", "2020-03-18"): "CRSP ret -16.96%, vol 20.7m (10.4m prior day); yfinance -16.96%; next day +8.32%",
}


def repair_bad_prints(df: pd.DataFrame) -> pd.DataFrame:
    """Replace known bad closing prints; recompute the print-day and next-day
    returns, preserving CRSP's dividend component (ret - retx)."""
    for (t, day), why in BAD_PRINTS.items():
        day = pd.Timestamp(day)
        y = yf.download(t, start=day - pd.Timedelta(days=7),
                        end=day + pd.Timedelta(days=7), auto_adjust=False,
                        progress=False)
        yclose = float(y["Close"].loc[day].iloc[0])
        sub = df[df["ticker"] == t].sort_values("date")
        i = sub.index[sub["date"] == day]
        assert len(i) == 1, f"{t} {day.date()}: bad-print row not found"
        i = i[0]
        pos = sub.index.get_loc(i)
        i_prev, i_next = sub.index[pos - 1], sub.index[pos + 1]
        prev_prc, next_prc = df.at[i_prev, "prc_adj"], df.at[i_next, "prc_adj"]
        assert abs(yclose / prev_prc - 1) < 0.05, \
            f"{t} {day.date()}: repair close {yclose} implausible vs prev {prev_prc}"
        old = (df.at[i, "ret_total"], df.at[i_next, "ret_total"], df.at[i, "prc_adj"])
        div_t = df.at[i, "ret_total"] - df.at[i, "ret_px"]
        div_n = df.at[i_next, "ret_total"] - df.at[i_next, "ret_px"]
        df.at[i, "prc_adj"] = yclose
        df.at[i, "ret_px"] = yclose / prev_prc - 1
        df.at[i, "ret_total"] = df.at[i, "ret_px"] + div_t
        df.at[i_next, "ret_px"] = next_prc / yclose - 1
        df.at[i_next, "ret_total"] = df.at[i_next, "ret_px"] + div_n
        print(f"  REPAIRED bad print {t} {day.date()} ({why}): prc {old[2]:.2f} -> "
              f"{yclose:.2f}; ret {old[0]:+.4f} -> {df.at[i, 'ret_total']:+.4f}; "
              f"next-day ret {old[1]:+.4f} -> {df.at[i_next, 'ret_total']:+.4f}")
    return df


def scan_reversals(df: pd.DataFrame, tickers=None) -> None:
    """Print (never alter) other bad-print candidates: |ret|>8% mostly reversed
    next day on thin volume. Repairs happen only via BAD_PRINTS."""
    for t in (TICKERS if tickers is None else tickers):
        sub = df[df["ticker"] == t].sort_values("date").reset_index(drop=True)
        r, nxt = sub["ret_total"], sub["ret_total"].shift(-1)
        cand = sub[(r.abs() > 0.08) & (((1 + r) * (1 + nxt) - 1).abs() < 0.3 * r.abs())
                   & (sub["volume"] < 50_000)]
        for _, row in cand.iterrows():
            if (t, row["date"].strftime("%Y-%m-%d")) not in BAD_PRINTS:
                print(f"  WARNING unrepaired reversal candidate {t} "
                      f"{row['date'].date()} ret {row['ret_total']:+.2%} "
                      f"vol {row['volume']:.0f} — review before trusting")


def load_crsp(permnos=None) -> pd.DataFrame:
    """`permnos` None = PERMNOS (the default build). `prc_signed` (CRSP prc as
    recorded) is selected always and written only by --xasset."""
    permnos = PERMNOS if permnos is None else permnos
    by_permno = {v["permno"]: t for t, v in permnos.items()}
    con = connect()
    dsf = r2_path("crsp_a_stock", "dsf")
    plist = ",".join(str(v["permno"]) for v in permnos.values())
    df = q(con, f"""
        SELECT date, permno,
               ret::DOUBLE          AS ret_total,
               retx::DOUBLE         AS ret_px,
               ABS(prc)::DOUBLE / cfacpr AS prc_adj,
               vol::DOUBLE          AS volume,
               prc::DOUBLE          AS prc_signed
        FROM read_parquet('{dsf}')
        WHERE permno IN ({plist})
        ORDER BY permno, date
    """)
    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["permno"].map(by_permno)

    print("--- CRSP leg (wrds/crsp_a_stock/dsf.parquet) ---")
    for t in permnos:
        exp = permnos[t]
        sub = df[df["ticker"] == t]
        d0, d1 = sub["date"].min(), sub["date"].max()
        assert (d0.date().isoformat(), d1.date().isoformat(), len(sub)) == \
            (exp["first"], exp["last"], exp["n"]), \
            f"{t}: dsf {d0.date()}..{d1.date()} n={len(sub)} != expected {exp}"
        nan_ret = sub[sub["ret_total"].isna()]
        assert list(nan_ret["date"]) == [d0], \
            f"{t}: NULL ret beyond inception day: {nan_ret['date'].tolist()}"
        assert sub["date"].is_unique
        assert sub["prc_adj"].notna().all() and (sub["prc_adj"] > 0).all()
        assert sub["volume"].notna().all()
        assert sub["prc_signed"].notna().all() and (sub["prc_signed"] != 0).all()
        print(f"  {t:<5} {d0.date()} -> {d1.date()}  {len(sub)} rows "
              f"(inception-day NaN ret dropped: 1; no-closing-trade prc < 0: "
              f"{int((sub['prc_signed'] < 0).sum())})")
    df = df.dropna(subset=["ret_total"]).reset_index(drop=True)
    df = repair_bad_prints(df)
    scan_reversals(df, list(permnos))
    return df


def load_yf(tickers=None) -> pd.DataFrame:
    tickers = TICKERS if tickers is None else tickers
    raw = yf.download(tickers, start=YF_START, auto_adjust=False, actions=True,
                      progress=False, group_by="ticker")
    assert raw is not None and not raw.empty, "yfinance returned nothing"
    frames = []
    print(f"\n--- yfinance leg (auto_adjust=False + actions; requested start {YF_START}) ---")
    for t in tickers:
        d = raw[t].dropna(subset=["Close"]).copy()
        assert not d.empty, f"{t}: empty yfinance frame"
        d.index = pd.to_datetime(d.index).tz_localize(None)
        # assert the returned range covers the request (standing fetch rule)
        assert d.index.min() <= pd.Timestamp(YF_START) + pd.Timedelta(days=5), \
            f"{t}: yfinance starts {d.index.min().date()}, requested {YF_START}"
        assert d.index.max() >= pd.Timestamp.today().normalize() - pd.Timedelta(days=7), \
            f"{t}: yfinance ends {d.index.max().date()} — stale fetch"
        splits = d.get("Stock Splits", pd.Series(0.0, index=d.index)).fillna(0)
        assert (splits == 0).all(), \
            f"{t}: stock split inside yfinance window — ret_px/prc_adj formulas must be extended"
        dist = d["Dividends"].fillna(0.0)
        if "Capital Gains" in d.columns:
            dist = dist + d["Capital Gains"].fillna(0.0)
        frames.append(pd.DataFrame({
            "date": d.index, "ticker": t,
            "ret_adjclose": d["Adj Close"].pct_change().to_numpy(),
            "ret_inhouse": ((d["Close"] + dist) / d["Close"].shift(1) - 1).to_numpy(),
            "ret_px": d["Close"].pct_change().to_numpy(),
            "prc_adj": d["Close"].to_numpy(dtype=float),
            "volume": d["Volume"].to_numpy(dtype=float),
            "dividend": dist.to_numpy(dtype=float),   # for the Alpaca cross-check only
        }))
        print(f"  {t:<5} {d.index.min().date()} -> {d.index.max().date()}  {len(d)} rows, "
              f"{int((dist > 0).sum())} distribution days")
    return pd.concat(frames, ignore_index=True)


def validate_splice(crsp: pd.DataFrame, yfd: pd.DataFrame, tickers=None) -> dict:
    """2024 overlap: CRSP ret vs both yfinance TR candidates. Returns per-ticker
    chosen method + diagnostics dict; raises if neither method passes."""
    print("\n--- 2024 overlap validation (CRSP ret vs yfinance TR candidates) ---")
    diag = {}
    for t in (TICKERS if tickers is None else tickers):
        a = crsp[(crsp.ticker == t) & (crsp.date.dt.year == 2024)].set_index("date")
        b = yfd[(yfd.ticker == t) & (yfd.date.dt.year == 2024)].set_index("date")
        missing_crsp = sorted(set(b.index) - set(a.index))
        missing_yf = sorted(set(a.index) - set(b.index))
        assert not missing_crsp and not missing_yf, \
            f"{t}: 2024 calendar mismatch crsp-missing={missing_crsp} yf-missing={missing_yf}"
        both = a[["ret_total"]].join(b[["ret_adjclose", "ret_inhouse"]]).dropna()
        stats = {}
        for m in ("ret_adjclose", "ret_inhouse"):
            dd = (both["ret_total"] - both[m]).abs()
            stats[m] = {"max_bp": dd.max() * 1e4, "mean_bp": dd.mean() * 1e4,
                        "worst_day": dd.idxmax().date()}
        # prefer the spec default (adjclose) when it passes, else inhouse
        method = "ret_adjclose" if stats["ret_adjclose"]["max_bp"] < SPLICE_MAX_BP \
            else "ret_inhouse"
        s = stats[method]
        assert s["max_bp"] < SPLICE_MAX_BP, (
            f"{t}: BOTH TR methods exceed {SPLICE_MAX_BP}bp on 2024 overlap — "
            f"adjclose max {stats['ret_adjclose']['max_bp']:.2f}bp "
            f"(worst {stats['ret_adjclose']['worst_day']}), "
            f"inhouse max {stats['ret_inhouse']['max_bp']:.2f}bp "
            f"(worst {stats['ret_inhouse']['worst_day']}) — investigate, do not accept"
        )
        diag[t] = {"method": method.replace("ret_", ""), **{
            k.replace("ret_", ""): v for k, v in stats.items()}}
        print(f"  {t:<5} n={len(both)}  "
              f"adjclose max/mean {stats['ret_adjclose']['max_bp']:.2f}/"
              f"{stats['ret_adjclose']['mean_bp']:.3f} bp "
              f"(worst {stats['ret_adjclose']['worst_day']})  |  "
              f"inhouse max/mean {stats['ret_inhouse']['max_bp']:.2f}/"
              f"{stats['ret_inhouse']['mean_bp']:.3f} bp  ->  using {diag[t]['method']}")
    return diag


def check_alpaca(crsp: pd.DataFrame, yfd: pd.DataFrame, diag: dict, tickers=None):
    """The Alpaca leg, from YF_START to yesterday, checked against CRSP on 2024
    (the yfinance leg's own gate) and against yfinance from ALPACA_CHECK_FROM.
    Returns the leg with in-house returns."""
    from scripts.rv import alpaca_daily as ad
    start = dt.date.fromisoformat(YF_START)
    alp = ad.inhouse_returns(ad.leg(ad.make_client(),
                                    TICKERS if tickers is None else tickers, start))
    print(f"\n--- alpaca leg (feed={ad.FEED}, adjustment={ad.ADJUSTMENT}) "
          f"{alp.date.min().date()} -> {alp.date.max().date()} ---")

    c = crsp.sort_values(["ticker", "date"]).copy()
    prev = c.groupby("ticker")["prc_adj"].shift(1)
    # CRSP's distribution, backed out of its two returns (exact by construction;
    # zero on every non-ex-date because ret == retx there)
    c["dividend"] = (c["ret_total"] - c["ret_px"]) * prev
    neg = c[(c["date"].dt.year == 2024) & (c["dividend"] < 0)]
    assert neg.empty, f"CRSP ret < retx in 2024 (a negative distribution?): {neg.head().to_dict('records')}"
    # first row per ticker has no previous price; it is outside the 2024 window
    c["dividend"] = c["dividend"].where(c["dividend"] > 0, 0.0)
    st = ad.compare_legs(alp, c, dt.date(2024, 1, 1), dt.date(2024, 12, 31),
                         ("ret_total",), SPLICE_MAX_BP, "alpaca vs CRSP ret (2024)")
    print("  vs CRSP 2024:")
    print(st[["ticker", "n", "n_ex", "ret_total_max_bp", "ret_total_worst"]].to_string(index=False))

    y = yfd.copy()
    y["ret_total"] = [r.ret_adjclose if diag[r.ticker]["method"] == "adjclose" else r.ret_inhouse
                      for r in y.itertuples()]
    st = ad.compare_legs(alp, y, dt.date.fromisoformat(ALPACA_CHECK_FROM), alp.date.max().date(),
                         ("ret_total",), SPLICE_MAX_BP, "alpaca vs yfinance")
    print(f"  vs yfinance {ALPACA_CHECK_FROM}..:")
    print(st[["ticker", "n", "n_ex", "max_div_diff", "ret_total_max_bp", "ret_total_worst",
              "unchecked_after"]].to_string(index=False))
    return alp


def check_large_moves(etf: pd.DataFrame, named=None) -> None:
    named = LARGE_MOVES if named is None else named
    big = etf.loc[etf["ret_total"].abs() >= LARGE_MOVE_BOUND, ["ticker", "date", "ret_total"]]
    seen = {(r.ticker, r.date.strftime("%Y-%m-%d")): r.ret_total for r in big.itertuples()}
    unnamed = {k: v for k, v in seen.items() if k not in named}
    assert not unnamed, (
        f"daily ETF return >= {LARGE_MOVE_BOUND:.0%} not in LARGE_MOVES: {unnamed} "
        "-- a data error until a second source says otherwise")
    gone = sorted(set(named) - set(seen))
    assert not gone, f"LARGE_MOVES rows no longer present (source changed?): {gone}"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT, help="default data/etf_daily.parquet")
    ap.add_argument("--xasset", action="store_true",
                    help="also the nine XASSET names and the prc_signed column; "
                         "--out must be outside data/")
    a = ap.parse_args(argv)
    out = a.out
    cols = ["date", "ticker", "permno", "ret_total", "ret_px", "prc_adj", "volume", "source"]
    permnos, named = PERMNOS, LARGE_MOVES
    if a.xasset:
        data_dir = (REPO / "data").resolve()
        o = out.resolve()
        if o == OUT.resolve() or data_dir in o.parents:
            raise SystemExit(f"--xasset refuses --out {out}: nothing it builds may land under "
                             f"data/ (src/backtest/engine.py reads data/etf_daily.parquet)")
        permnos = {**PERMNOS, **XASSET_PERMNOS}
        named = {**LARGE_MOVES, **XASSET_LARGE_MOVES}
        cols = cols + ["prc_signed"]
    tickers = list(permnos)
    out.parent.mkdir(parents=True, exist_ok=True)
    yf_last = pd.Timestamp(YF_LAST)

    crsp = load_crsp(permnos)
    yfd = load_yf(tickers)
    diag = validate_splice(crsp, yfd, tickers)
    alp = check_alpaca(crsp, yfd, diag, tickers)

    print("\n--- splice ---")
    parts = [crsp.assign(source="crsp")[cols]]
    for t in tickers:
        last_crsp = crsp.loc[crsp.ticker == t, "date"].max()
        yft = yfd[yfd.ticker == t]
        tail = yft[(yft.date > last_crsp) & (yft.date <= yf_last)].copy()
        prev_bar = yft.loc[yft.date < tail["date"].min(), "date"].max()
        assert prev_bar == last_crsp, \
            f"{t}: splice seam gap — yfinance bar before splice is {prev_bar.date()}, " \
            f"CRSP ends {last_crsp.date()}"
        assert tail["date"].max() == yf_last, \
            f"{t}: yfinance has no bar on the Alpaca seam {YF_LAST}"
        tail["ret_total"] = tail["ret_adjclose" if diag[t]["method"] == "adjclose"
                                 else "ret_inhouse"]
        tail["permno"] = permnos[t]["permno"]
        tail["source"] = "yfinance"
        assert tail["ret_total"].notna().all()
        if a.xasset:
            tail["prc_signed"] = np.nan     # no CRSP record outside the CRSP leg
        parts.append(tail[cols])
        # Alpaca after the seam; its first return accrues from ALPACA's own
        # seam-day close (in the leg), as yfinance's first return accrued from
        # yfinance's own bar on the CRSP end date.
        at = alp[(alp.ticker == t) & (alp.date > yf_last)]
        at = pd.DataFrame({"date": at["date"], "ticker": t, "permno": permnos[t]["permno"],
                           "ret_total": at["ret_total"], "ret_px": at["ret_px"],
                           "prc_adj": at["close"], "volume": at["volume"], "source": "alpaca"})
        assert at["ret_total"].notna().all()
        if a.xasset:
            at["prc_signed"] = np.nan       # no CRSP record outside the CRSP leg
        parts.append(at)
        print(f"  {t:<5} CRSP ends {last_crsp.date()}, yfinance takes over "
              f"{tail['date'].min().date()} ({len(tail)} rows, TR method: {diag[t]['method']}), "
              f"alpaca from {at['date'].min().date() if len(at) else '-'} ({len(at)} rows)")

    etf = (pd.concat(parts, ignore_index=True)
           .sort_values(["ticker", "date"])
           .reset_index(drop=True))
    etf["date"] = pd.to_datetime(etf["date"])
    etf["permno"] = etf["permno"].astype("int64")

    assert not etf.duplicated(["ticker", "date"]).any()
    assert etf[["ret_total", "ret_px", "prc_adj", "volume"]].notna().all().all()
    check_large_moves(etf, named)
    if a.xasset:
        crsp_rows = etf["source"] == "crsp"
        assert etf.loc[crsp_rows, "prc_signed"].notna().all()
        assert etf.loc[~crsp_rows, "prc_signed"].isna().all()
        # prc_adj is |prc|/cfacpr: same magnitude ordering, and never negative
        assert (etf["prc_adj"] > 0).all()
        neg = etf[etf["prc_signed"] < 0].groupby("ticker").size()
        print(f"\n--- prc_signed: no-closing-trade rows (CRSP prc < 0) by ticker ---\n"
              f"  {neg.to_dict()}")

    print("\n--- final panel ---")
    for t in tickers:
        sub = etf[etf.ticker == t].set_index("date")["ret_total"]
        ann = (1 + sub).prod() ** (252 / len(sub)) - 1
        vol = sub.std() * np.sqrt(252)
        print(f"  {t:<5} {sub.index.min().date()} -> {sub.index.max().date()}  "
              f"{len(sub)} rows  annTR {ann:+.2%}  annVol {vol:.2%}  "
              f"max|ret| {sub.abs().max():.2%}")

    etf.to_parquet(out, index=False)
    src_counts = etf.groupby("source").size().to_dict()
    print(f"\nwrote {out} ({len(etf)} rows; {etf.date.min().date()} -> "
          f"{etf.date.max().date()}; {src_counts})")


if __name__ == "__main__":
    main()
