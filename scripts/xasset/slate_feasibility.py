"""Zero-trial feasibility for the XASSET slate (RESEARCH_PLAN_2026-10-09 gate G8).

    python3 scripts/xasset/slate_feasibility.py                 # panels + bar and power arithmetic
    export QUANTT_ENV_FILE=/abs/path/to/config/.env             # never printed
    python3 scripts/xasset/slate_feasibility.py --alpaca        # + read-only asset flags
    python3 scripts/xasset/slate_feasibility.py --crsp          # + CRSP coverage (R2 mirror)
    python3 scripts/xasset/slate_feasibility.py --factors       # + AQR factor-file coverage

WHY THIS EXISTS
---------------
Gate G8 declares the five cross-asset tests X1-X5 in one pre-registration
(`results/xasset/PREREG_XASSET_SLATE_2026-10-12.md`) BEFORE any of them runs, so
the XASSET counter's N (and its sqrt(2 ln N) bar) is fixed in advance. Declaring
a test needs three facts that do not spend it:

1. does the repo hold every instrument the test names, from which date, with
   which interior gaps, and to which last date (stale is a form of wrong);
2. can the instrument be traded (and, where the test shorts it, shorted) at
   Alpaca today -- `shortable` changes daily (CLAUDE.md landmine 5), so every
   row carries the UTC time it was read and is true on that date only;
3. given each test's declared eligibility rule, how many fit-period years it
   has before the sealed 2023-01-01 holdout, and therefore what Sharpe the bar
   demands. That is arithmetic on the BAR, not on any return: the required
   Sharpe is found by inverting `scripts/cef/validate.py::_dsr` (the repo's only
   implementation of the deflated-Sharpe bar) at zero skew and normal kurtosis.

4. POWER (added 2026-10-12, with the team lead's rulings on the draft): at
   each test's fit length, the Sharpe it must show to pass, the Sharpe at which
   it would pass four times in five, and the probability of passing if the true
   Sharpe were the published one, or the published one cut by McLean and
   Pontiff's 58% post-publication decline (docs/REFERENCES.md §12b). This is
   arithmetic on published numbers, so a null result can be read: a test that
   cannot pass at its published Sharpe teaches little when it fails.

   REVISED 2026-10-13 (pre-registration revision 3, the adversarial review's
   fix 8). Three things were wrong with the first version:
   (a) T was the count of sessions after the first decision. Under shift(2)
       the first P&L is earned two sessions after the first decision, so T is
       now the P&L session count (`pnl_window`), the same T the trial passes
       to `_dsr`;
   (b) SE(annual SR) was 1/sqrt(years), a second, simpler copy of the
       sampling error. It is now `_dsr`'s own denominator at skew 0 and
       kurtosis 3 (`sr_se`, tested against `_dsr`'s z), so the bar and the
       error around it come from one function;
   (c) power was quoted only at the published Sharpe, which for X2 is HMM's
       in-sample 1.11 with no execution delay. Each test is now also powered
       at the draft's OWN expected range (EXPECTED_SR), and the published
       figure is printed as an upper reference.
   The D4 column now uses the BINDING regression window: where two R-D4
   regressions are declared (the test starts before HYG), the shorter one,
   from HYG's first return, is the one that must clear alpha t >= 3.
5. `--crsp`: each slate instrument's CRSP identity (`stocknames`, share code
   73), and in `dsf` its first and last date, row count, NULL-`ret` count,
   negative-`prc` count (no closing trade: CRSP stores minus the bid/ask
   average) and zero-volume count. These are coverage and quality COUNTS. No
   `ret` value is read into Python.
6. `--factors`: the AQR Time Series Momentum and Value and Momentum Everywhere
   factor files are reachable, with their column names and first and last month.
   The download goes to a temporary directory that is deleted, and no factor
   value is printed.

WHAT IT MUST NEVER DO
---------------------
Compute a strategy return, Sharpe, IC, turnover or any statistic of an X-test.
That would spend the trial before the slate is declared. It reads the
`ret_total` column only to find where it is non-missing (coverage). No return
is summed, averaged, signed or combined. `ret_total` values are never printed.

INPUTS (read-only; `data/` is what the live sleeve decides on, landmine 9)
-------------------------------------------------------------------------
`data/rv/etf_panel.parquet` (34 tickers) and `data/rv/etf_ohlc_extended.parquet`
(60 tickers): in-house total return (close + distribution) / previous close - 1,
yfinance up to each fetcher's YF_LAST and Alpaca SIP bars after it
(docs/REFERENCES.md §8, fetchers `scripts/rv/stage_universe.py`,
`stage_ohlc_extended.py`). `data/etf_daily.parquet` (13 tickers; CRSP to
2024-12-31) is reported beside them as the second source where it exists.
The master session calendar is SPY's row set in `etf_panel` (SPY trades every
NYSE session from 1993-02-01).

OUTPUT
------
`results/xasset/feasibility/slate_feasibility_<date>.csv`, one row per instrument: panel,
first and last non-missing `ret_total` date, interior gap count against the
master calendar, the CRSP-panel first date where it exists, and (with
`--alpaca`) name / status / tradable / shortable / easy_to_borrow / borrow_status /
exchange / marginable / fractionable with the UTC read time. It carries no
account identifier (the asset endpoint returns none). The per-test fit windows
and required Sharpes are printed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

HOLDOUT_START = pd.Timestamp("2023-01-01")       # H13: sealed; nothing here reads past it
# Revision 3 (fix 5): the holdout ends here for all five tests, fixed before any
# run, so its length is not chosen by when a test happens to be run. Used only to
# COUNT sessions (the false-kill arithmetic); no return in it is read.
HOLDOUT_END = pd.Timestamp("2026-09-30")
FEASIBILITY_DIR = REPO / "results/xasset/feasibility"   # the snapshot's folder (note on top, data below)
PANELS = {
    "etf_panel": REPO / "data/rv/etf_panel.parquet",
    "etf_ohlc_extended": REPO / "data/rv/etf_ohlc_extended.parquet",
}
CRSP_PANEL = REPO / "data/etf_daily.parquet"

# The slate, exactly as declared in the pre-registration. Changing a list here
# after the declaration is approved changes the trial; it needs a dated note.
X1 = ["HYG", "LQD", "IEF", "TLT", "EMB", "PFF", "MUB", "BKLN", "CWB"]
X4 = X1 + ["SPY", "EFA", "EEM", "GLD", "DBC"]
# X5 is a dollar-neutral cross-section, so it takes X1's names that could be
# shorted on the declaration snapshot (MUB was not, 2026-10-12). Declared, not
# measured: a later flip in MUB's flag does not change the trial's universe.
X5 = [s for s in X1 if s != "MUB"]
X5_TREASURY_CONTROL = ["SHY", "IEI", "IEF", "TLH", "TLT"]
TESTS = {
    # name: (traded instruments, eligibility lag in months, breadth rule)
    "X1": (X1, 12, "half"),
    "X2": (["SPY", "IEF"], 1, "all"),
    "X3": (["IEF"], 1, "all"),
    "X4": (X4, 12, "half"),
    "X5": (X5, 36, "half"),
}
CONTROLS = ["SHY", "BIL", "IEI", "TLH", "AGG"]   # controls and factor proxies named in the prereg

# The published Sharpe each test is powered against (docs/REFERENCES.md §12i).
# Out-of-sample figures where the paper gives one. An INPUT TO THE POWER
# ARITHMETIC ONLY: no decision rule reads it (H14).
PUBLISHED_SR = {
    "X1": (0.49, "BSV Table IV Panel A, bond trend, new sample"),
    "X2": (1.11, "HMM Table 6, 1997-2023, in-sample"),
    "X3": (0.88, "Hartley-Schwarz Table 3, 10-year, t=3, 1990-2018"),
    "X4": (0.98, "BSV Table IV Panel A, multi-asset trend, new sample"),
    "X5": (0.31, "BSV Table IV Panel A, bond momentum, new sample"),
}
MCLEAN_PONTIFF_KEEP = 0.42     # 1 - 0.58: "58% lower after publication" (REFERENCES §12b, [V] abstract)
# The draft's OWN expected gross Sharpe range for each test, [U] in its section
# (PREREG §4-§8 "Expectation"), as (low, high). Added in revision 3 (fix 8): the
# published figures are upper references (HMM's is in-sample with no delay; BSV's
# multi-asset figure is a many-market composite), so power is stated at the
# range the draft itself expects. X3's section gives no number ("near the
# published Sharpe in 2002-2018, smaller after it"), so its bracket is 0.42x the
# published figure to the published figure. An INPUT TO THE POWER ARITHMETIC
# ONLY: no decision rule reads it (H14).
EXPECTED_SR = {
    "X1": (0.30, 0.60, "PREREG §4"),
    "X2": (0.20, 0.80, "PREREG §5"),
    "X3": (round(0.88 * MCLEAN_PONTIFF_KEEP, 2), 0.88, "PREREG §6 is qualitative; bracket 0.42x published .. published"),
    "X4": (0.40, 0.80, "PREREG §7"),
    "X5": (0.00, 0.40, "PREREG §8"),
}
# The D4 factor whose history starts last: HY = HYG - IEF. A test whose first P&L
# session precedes HYG's first return carries two R-D4 regressions (PREREG §1.7),
# and the shorter one, from HYG's first return, binds.
D4_LATE_FACTOR = "HYG"
AQR_FILES = {
    "TSMOM": "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Time-Series-Momentum-Factors-Monthly.xlsx",
    "VME": "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Value-and-Momentum-Everywhere-Factors-Monthly.xlsx",
}


def coverage(sym: str, frames: dict, cal: pd.DatetimeIndex) -> dict:
    """Where `sym`'s ret_total is non-missing, and how many master sessions inside
    its own [first, last] carry no value. Raises if no panel holds it."""
    for name, df in frames.items():
        s = df.loc[df["ticker"] == sym].set_index("date")["ret_total"]
        if s.notna().any():
            s = s[s.notna()]
            first, last = s.index.min(), s.index.max()
            inside = cal[(cal >= first) & (cal <= last)]
            gaps = int((~inside.isin(s.index)).sum())
            return dict(symbol=sym, panel=name, first=first.date(), last=last.date(),
                        sessions=len(s), interior_gaps=gaps)
    raise KeyError(f"{sym}: no non-missing ret_total in any of {list(frames)}; "
                   f"the test that names it cannot be built from repo data")


def month_ends(cal: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last NYSE session of each calendar month, from the master calendar."""
    s = pd.Series(cal, index=cal)
    return pd.DatetimeIndex(s.groupby([cal.year, cal.month]).max().values)


def fit_window(syms, lag_m: int, rule: str, firsts: dict, cal: pd.DatetimeIndex):
    """First month-end E at which the declared breadth rule holds, where an
    instrument is eligible at E once its first return is on or before the first
    session after the month-end `lag_m` months earlier (a full lookback window).
    `half` = at least ceil(n/2) eligible (MOP p.236 starts its evaluation once
    "a comprehensive set of instruments have data"; ceil(n/2) is this desk's
    mechanical stand-in, declared before any return is seen); `all` = every one."""
    me = month_ends(cal)
    need = math.ceil(len(syms) / 2) if rule == "half" else len(syms)
    for i in range(lag_m, len(me)):
        start_of_window = cal[cal > me[i - lag_m]][0]
        n_ok = sum(pd.Timestamp(firsts[s]) <= start_of_window for s in syms)
        if n_ok >= need:
            fit = cal[(cal > me[i]) & (cal < HOLDOUT_START)]
            return me[i].date(), len(fit), need
    raise RuntimeError(f"breadth rule {rule} never holds for {syms}")


def required_sharpe(n_trials: int, n_days: int) -> float:
    """Annualised Sharpe at which validate._dsr == 0.95 (its PASS line), skew 0,
    kurtosis 3. Bisection on the repo's own function: no second copy of the bar."""
    from scripts.cef.validate import _dsr
    lo, hi = 0.0, 5.0
    for _ in range(60):
        mid = (lo + hi) / 2
        d, _, _ = _dsr(mid, n_days, 0.0, 3.0, n_trials)
        lo, hi = (mid, hi) if d < 0.95 else (lo, mid)
    return hi


def pnl_window(first_dec, cal: pd.DatetimeIndex, start=None) -> tuple:
    """(first P&L session, number of P&L sessions before the holdout).

    Under H1 a position decided at the close of `first_dec` fills at the next
    close and earns the session after that, so the first P&L session is
    `first_dec` + EXEC_LAG sessions (validate.EXEC_LAG, not a second copy).
    `start` (e.g. a factor's first return) moves the window's start later,
    never earlier. This T is what the trial passes to `_dsr`: the P&L from the
    first P&L session to 2022-12-30, never `evaluate()['gross_sr']`, which
    averages over the flat sessions before the first decision as well."""
    from scripts.cef.validate import EXEC_LAG
    i = cal.get_loc(pd.Timestamp(first_dec))
    first_pnl = cal[i + EXEC_LAG]
    if start is not None:
        first_pnl = max(first_pnl, cal[cal >= pd.Timestamp(start)][0])
    n = int(((cal >= first_pnl) & (cal < HOLDOUT_START)).sum())
    return first_pnl.date(), n


def sr_se(sr_annual: float, n_days: int) -> float:
    """Sampling SE of an annualised Sharpe from `n_days` daily returns, exactly as
    `validate._dsr`'s denominator states it at skew 0 and kurtosis 3:
    sqrt(252) * sqrt(1 + (3-1)/4 * (SR/sqrt(252))^2) / sqrt(T-1).
    test_slate_feasibility holds this equal to the z `_dsr` computes, so the bar
    and the error around it come from one function."""
    sr_d = sr_annual / math.sqrt(252)
    return math.sqrt(252) * math.sqrt(1 + 0.5 * sr_d ** 2) / math.sqrt(n_days - 1)


def power(sr_true: float, n_trials: int, n_days: int) -> float:
    """P(validate._dsr > 0.95) when the true annual Sharpe is `sr_true`: the
    observed Sharpe is N(sr_true, sr_se(sr_true)) and passes when it exceeds the
    Sharpe at which `_dsr` reaches 0.95 (`_dsr` rises with the observed Sharpe)."""
    from statistics import NormalDist
    req = required_sharpe(n_trials, n_days)
    return NormalDist().cdf((sr_true - req) / sr_se(sr_true, n_days))


def sharpe_for_power(p: float, n_trials: int, n_days: int) -> float:
    """The true annual Sharpe at which `power` equals `p` (bisection)."""
    lo, hi = -2.0, 6.0
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if power(mid, n_trials, n_days) < p else (lo, mid)
    return hi


def alpha_t_bar(n_days: int, t: float = 3.0) -> float:
    """The annual information ratio at which a t of `t` is reached: t * sqrt(252/T)."""
    return t * math.sqrt(252 / n_days)


def p_alpha_t(ir_true: float, n_days: int, t: float = 3.0) -> float:
    """P(alpha t >= `t`) at a true annual information ratio `ir_true`, with the
    same sampling SE as `power`. The ALPHA LEG of D4 only: the beta leg
    (every |beta| <= 0.10) is a condition on the sleeve's true exposures, not on
    sampling, so this is an upper bound on P(D4 pass)."""
    from statistics import NormalDist
    return NormalDist().cdf((ir_true - alpha_t_bar(n_days, t)) / sr_se(ir_true, n_days))


def crsp_coverage(symbols) -> pd.DataFrame:
    """CRSP identity and dsf coverage/quality COUNTS for each symbol (share code
    73, ETFs). A ticker with no share-code-73 record, or with two permnos at
    once, raises. No return value leaves the database."""
    from src.data import r2
    cfg = r2.load_config()
    con = r2.connect(cfg)
    names = con.execute(
        f"SELECT permno, ticker, namedt, nameenddt, shrcd FROM "
        f"read_parquet('{r2.r2_path('crsp_a_stock', 'stocknames', cfg)}') "
        f"WHERE ticker IN ({','.join('?' * len(symbols))}) AND shrcd = 73", list(symbols)).df()
    rows = []
    for sym in symbols:
        rec = names[names.ticker == sym]
        if rec.empty:
            raise KeyError(f"{sym}: no CRSP stocknames record with share code 73")
        if rec.permno.nunique() != 1:
            raise RuntimeError(f"{sym}: {rec.permno.nunique()} permnos carry this ticker as an ETF: "
                               f"{sorted(rec.permno.unique())}; resolve by date before use")
        permno = int(rec.permno.iloc[0])
        c = con.execute(
            f"SELECT MIN(date), MAX(date), COUNT(*), "
            f"SUM(CASE WHEN ret IS NULL THEN 1 ELSE 0 END), "
            f"SUM(CASE WHEN prc < 0 THEN 1 ELSE 0 END), "
            f"SUM(CASE WHEN vol = 0 THEN 1 ELSE 0 END) "
            f"FROM read_parquet('{r2.r2_path('crsp_a_stock', 'dsf', cfg)}') WHERE permno = ?",
            [permno]).fetchone()
        rows.append(dict(symbol=sym, crsp_permno=permno, crsp_first=pd.Timestamp(c[0]).date(),
                         crsp_last=pd.Timestamp(c[1]).date(), crsp_rows=int(c[2]),
                         crsp_null_ret=int(c[3]), crsp_neg_prc=int(c[4]), crsp_zero_vol=int(c[5])))
    return pd.DataFrame(rows)


def factor_file_coverage() -> list[str]:
    """Reach each AQR factor file; report columns and first/last month only."""
    import tempfile
    import urllib.request
    out = []
    ua = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    with tempfile.TemporaryDirectory() as tmp:
        for name, url in AQR_FILES.items():
            path = Path(tmp) / f"{name}.xlsx"
            with urllib.request.urlopen(urllib.request.Request(url, headers=ua), timeout=60) as r:
                path.write_bytes(r.read())
            book = pd.ExcelFile(path)
            df = book.parse(book.sheet_names[0], header=None)
            hdr = next((i for i in range(min(60, len(df)))
                        if any(str(v).strip().upper() in ("DATE", "TSMOM") for v in df.iloc[i])), None)
            if hdr is None:
                raise RuntimeError(f"{name}: no header row found; the file layout changed -- look at it")
            cols = [str(v).strip() for v in df.iloc[hdr] if str(v).strip() not in ("nan", "DATE")]
            dates = pd.to_datetime(df.iloc[hdr + 1:, 0], errors="coerce").dropna()
            out.append(f"{name}: sheet '{book.sheet_names[0]}', {len(dates)} months "
                       f"{dates.min().date()} .. {dates.max().date()}; columns {cols[:8]}")
    return out


def alpaca_flags(symbols) -> pd.DataFrame:
    """GET /v2/assets/{symbol} on the cef paper key (read-only). A 404 is a finding."""
    from quantt.broker.alpaca import AlpacaClient, AssetNotFound
    client = AlpacaClient.from_environment("cef")   # raises if QUANTT_ENV_FILE is unset
    fields = ("name", "status", "exchange", "tradable", "shortable", "easy_to_borrow",
              "borrow_status", "marginable", "fractionable")
    rows = []
    for sym in symbols:
        t = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        try:
            a = client.asset(sym)
            rows.append({"symbol": sym, "alpaca_read_utc": t, "found": True,
                         **{f: a.get(f) for f in fields}})
        except AssetNotFound:
            rows.append({"symbol": sym, "alpaca_read_utc": t, "found": False})
    return pd.DataFrame(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--alpaca", action="store_true", help="also read Alpaca asset flags (read-only)")
    ap.add_argument("--crsp", action="store_true", help="also read CRSP coverage counts from the R2 mirror")
    ap.add_argument("--factors", action="store_true", help="also check the AQR factor files are reachable")
    ap.add_argument("--out", default=None, help="CSV path (default results/xasset/feasibility/slate_feasibility_<today>.csv)")
    a = ap.parse_args(argv)

    frames = {}
    for name, path in PANELS.items():
        df = pd.read_parquet(path, columns=["date", "ticker", "ret_total"])
        df["date"] = pd.to_datetime(df["date"])
        frames[name] = df
        print(f"{name}: last date {df['date'].max().date()}  ({path.relative_to(REPO)})")
    cal = pd.DatetimeIndex(sorted(frames["etf_panel"].loc[frames["etf_panel"]["ticker"] == "SPY", "date"].unique()))
    crsp = pd.read_parquet(CRSP_PANEL, columns=["date", "ticker", "source"])
    crsp_first = crsp.groupby("ticker")["date"].min()
    print(f"etf_daily (CRSP <= 2024-12-31): last date {crsp['date'].max().date()}")

    syms = list(dict.fromkeys(X4 + CONTROLS))
    cov = pd.DataFrame([coverage(s, frames, cal) for s in syms])
    cov["crsp_panel_first"] = [crsp_first[s].date() if s in crsp_first else None for s in syms]
    if a.crsp:
        cov = cov.merge(crsp_coverage(syms), on="symbol", how="left")
    if a.alpaca:
        cov = cov.merge(alpaca_flags(syms), on="symbol", how="left")
    pd.set_option("display.width", 220)
    print(cov.to_string(index=False))

    firsts = dict(zip(cov["symbol"], cov["first"]))
    from statistics import NormalDist
    print("\nper test: first decision month-end under its declared rule; P&L sessions T from the"
          "\nfirst decision + 2 sessions (H1) to 2022-12-30; the Sharpe validate._dsr needs for 0.95"
          "\n(skew 0, kurt 3) at N = 5/4/3/2; the agenda's sqrt(2 ln N)/sqrt(years) reading at N = 5;"
          "\nand the LEGACY reading at N = 162 for reference (agenda section 6, item 1)")
    hy_first = firsts[D4_LATE_FACTOR]
    for name, (s, lag, rule) in TESTS.items():
        first_dec, _, need = fit_window(s, lag, rule, firsts, cal)
        first_pnl, T = pnl_window(first_dec, cal)
        yrs = T / 252
        req = {n: required_sharpe(n, T) for n in (5, 4, 3, 2)}
        sr0 = math.sqrt(2 * math.log(5)) / math.sqrt(yrs)
        legacy = required_sharpe(162, T)
        print(f"  {name}: n={len(s)} need {need} eligible (lag {lag}m); first decision {first_dec}; "
              f"first P&L {first_pnl}; T {T} sessions = {yrs:.2f} yr; required SR "
              + " ".join(f"N{n}:{v:.2f}" for n, v in req.items())
              + f"; sr0@N5 {sr0:.2f}; LEGACY N162 {legacy:.2f}")
        lo, hi, why = EXPECTED_SR[name]
        mid = (lo + hi) / 2
        print(f"      power at N=5 (SE from _dsr): Sharpe for 80% power {sharpe_for_power(0.80, 5, T):.2f}; "
              f"P(pass) at the draft's expected {lo:.2f} / {mid:.2f} / {hi:.2f} ({why}): "
              f"{power(lo, 5, T):.3f} / {power(mid, 5, T):.3f} / {power(hi, 5, T):.3f}")
        pub, src = PUBLISHED_SR[name]
        print(f"      upper reference: P(pass | published {pub:.2f}, {src}) {power(pub, 5, T):.3f}; "
              f"P(pass | {MCLEAN_PONTIFF_KEEP:.2f} x that = {pub * MCLEAN_PONTIFF_KEEP:.2f}) "
              f"{power(pub * MCLEAN_PONTIFF_KEEP, 5, T):.3f}")
        # D4 (alpha leg only): the binding regression is the shorter one where two are declared.
        two = pd.Timestamp(first_pnl) < pd.Timestamp(hy_first)
        d4_first, T_d4 = pnl_window(first_dec, cal, start=hy_first) if two else (first_pnl, T)
        print(f"      D4 alpha leg: {'two regressions; binding from ' + str(d4_first) if two else 'one regression'}"
              f", T {T_d4} = {T_d4 / 252:.2f} yr; alpha t >= 3 needs IR >= {alpha_t_bar(T_d4):.2f}; "
              f"P(alpha t >= 3) at IR {lo:.2f} / {mid:.2f} / {hi:.2f}: "
              f"{p_alpha_t(lo, T_d4):.3f} / {p_alpha_t(mid, T_d4):.3f} / {p_alpha_t(hi, T_d4):.3f}; "
              f"at published {pub:.2f}: {p_alpha_t(pub, T_d4):.3f}")
    # X5's Treasury-ladder control under its own breadth rule (revision 3, fix 9).
    lad_dec, _, lad_need = fit_window(X5_TREASURY_CONTROL, 36, "half", firsts, cal)
    lad_all, _, _ = fit_window(X5_TREASURY_CONTROL, 36, "all", firsts, cal)
    print(f"  X5 ladder control {X5_TREASURY_CONTROL}: need {lad_need} eligible (lag 36m); "
          f"first decision {lad_dec}; all five eligible from {lad_all}")
    # X2's SHY/BIL control: both Sharpes on the window from BIL's first return (fix 3).
    bil_first = pd.Timestamp(firsts["BIL"])
    n_bil = int(((cal >= bil_first) & (cal < HOLDOUT_START)).sum())
    print(f"  X2 control window: from BIL's first return {bil_first.date()} to 2022-12-30, "
          f"{n_bil} sessions = {n_bil / 252:.2f} yr")
    hold = cal[(cal >= HOLDOUT_START) & (cal <= HOLDOUT_END)]
    hy = len(hold) / 252
    print(f"  holdout {hold[0].date()} .. {hold[-1].date()}: {len(hold)} sessions = {hy:.2f} yr; "
          f"P(holdout mean has the wrong sign | true SR 0.5) = Phi(-0.5 sqrt(yr)) = "
          f"{NormalDist().cdf(-0.5 * math.sqrt(hy)):.3f}")
    if a.factors:
        print("\nfactor files (coverage only; no value printed):")
        for line in factor_file_coverage():
            print("  " + line)

    if not a.out:
        FEASIBILITY_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(a.out) if a.out else FEASIBILITY_DIR / f"slate_feasibility_{dt.date.today():%Y-%m-%d}.csv"
    cov.to_csv(out, index=False)
    print(f"\nwrote {out.relative_to(REPO) if out.is_relative_to(REPO) else out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
