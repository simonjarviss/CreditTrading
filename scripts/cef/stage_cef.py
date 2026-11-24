"""Credit closed-end funds: price and NAV history.

WHY CEFs, AFTER THE ETF PREMIUM/DISCOUNT TRADE DIED. An ETF has authorised
participants who can create and redeem shares against the underlying basket, and
that machine is exactly what compressed the HYG/JNK dislocation from 188bp in
2008 to 3.8bp today. We measured the corpse.

A closed-end fund has NO such machine. Its share count is fixed at IPO. Nothing
mechanically pulls the price toward net asset value, so credit CEFs trade at
discounts of 5-20% -- hundreds of times wider than any ETF gap -- and those
discounts persist and revert. Same asset class, same economic question, entirely
different plumbing, and the specific force that killed the ETF version does not
exist here.

Yahoo carries CEF NAVs under the legacy NASDAQ convention X<TICKER>X (NVG -> XNVGX).

Universe is credit ONLY: municipal, high yield, bank loan, EM debt, and
multi-sector credit. No equity CEFs, no covered-call funds.

WHO RUNS THIS (read 2026-10-28). A human, once, to build a fresh `data/`
(README "Commands", docs/ONBOARDING.md 2.4); fetch_daily refuses to run until
it has. No scheduled job, no session step and no collector step runs it, so it
is not on the live path. Its output can still reach prod at one remove: a prod
with no panels is seeded by COPYING them, by install_prod from the dev tree and
by install_vm from `--seed-from` (quantt/deploy, SEED_FILES), and fetch_daily
only ever revisits the last `--period` of a panel, so an empty row staged here
years back would stay in what the sleeve reads.

EMPTY ROWS (2026-10-28; scripts/cef/fetch_daily.py, EMPTY ROWS and EMPTY NAV
ROWS). This is the same yfinance `history()` call, which emits a row with every
price NaN and volume 0 for a dividend or split dated where there is no bar; by
2026-10-15 such rows had replaced 15 good 2026-09-15 bars in the laptop panel.
Rows were written here unchecked. Now a row with no finite close, or no finite
positive NAV, is not written, and each is printed (`NO CLOSE` / `NO NAV`, ticker, date,
why), by fetch_daily's own tests (`has_close`, `has_nav`); MIN_DAYS and MIN_NAV
count only rows that pass them. With no empty rows the files are byte-identical
to before (scripts/cef/tests/test_stage_cef_empty_rows.py).
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:            # run as a script, not -m
    sys.path.insert(0, str(REPO))
from ops.common import atomic_write      # noqa: E402
# One test for an empty row, shared with the daily refresh (EMPTY ROWS).
from scripts.cef.fetch_daily import has_close, has_nav  # noqa: E402
OUT = REPO / "data" / "cef"
OUT.mkdir(parents=True, exist_ok=True)

UNIVERSE = {
    "muni":  ["NVG", "NEA", "NAD", "NZF", "MYD", "MQY", "VKQ", "VMO", "NAN",
              "NXP", "MUE", "MHD", "MFM", "BFK", "BTA", "MVF", "NIM", "PMM"],
    "hy":    ["HYT", "HIO", "HIX", "DHY", "AWF", "ISD", "EAD", "GHY", "HYB",
              "PHD", "BGH", "HNW"],
    "loan":  ["BGT", "EFT", "EFR", "JFR", "JRO", "VVR", "NSL", "FCT", "BSL"],
    "emd":   ["EMD", "MSD", "TEI", "EDD", "EDF", "EDI"],
    "multi": ["PDI", "PTY", "PCN", "PFN", "PFL", "DSL", "DBL", "JPS", "PHK",
              "PDO", "PCI", "PKO", "BIT", "BGB", "HFRO"],
}
MIN_DAYS = 750          # ~3 years of price history
MIN_NAV = 200           # a NAV series short of this is not usable


def _n_with(frame, test, col: str) -> int:
    """How many of yfinance's rows in `frame` pass `test` (`has_close` /
    `has_nav`) once its 'Close' is named `col`. An empty row is not a day of
    history (EMPTY ROWS); with none, this is len(frame), the old count."""
    if not len(frame):
        return 0
    return int(test(frame.rename(columns={"Close": col})).sum())


def grab(tk: str):
    px = yf.Ticker(tk).history(period="max", auto_adjust=False)
    if _n_with(px, has_close, "close") < MIN_DAYS:
        return None, None
    nav = yf.Ticker(f"X{tk}X").history(period="max", auto_adjust=False)
    if _n_with(nav, has_nav, "nav") < MIN_NAV:
        return px, None
    return px, nav


def drop_empty(tk: str, p, n) -> tuple:
    """(p, n) without the rows that carry no finite close / no finite positive NAV,
    each printed by ticker, date and why (module docstring, EMPTY ROWS).
    Nothing is filled: the date is simply absent for that name. A frame with
    no empty row is returned untouched, so the files written are the bytes
    they were."""
    ok_p, ok_n = has_close(p), has_nav(n)
    for r in p.loc[~ok_p].itertuples(index=False):
        print(f"  {'NO CLOSE':<8} {tk:<6} {r.date.date()} (close {r.close}, volume "
              f"{r.volume}) not written: yfinance's row for this date has no close")
    for r in n.loc[~ok_n].itertuples(index=False):
        print(f"  {'NO NAV':<8} {tk:<6} {r.date.date()} (nav {r.nav}) not written: "
              f"yfinance's row for this date has no NAV")
    return (p if ok_p.all() else p.loc[ok_p]), (n if ok_n.all() else n.loc[ok_n])


def main() -> int:
    rows, navs, meta = [], [], []
    for grp, tickers in UNIVERSE.items():
        for tk in tickers:
            try:
                px, nav = grab(tk)
            except Exception as e:
                print(f"  ERR {tk:<6} {type(e).__name__}")
                continue
            if px is None:
                print(f"  skip {tk:<6} price history too short")
                continue
            if nav is None:
                print(f"  skip {tk:<6} no usable NAV feed")
                continue
            p = px.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
            p.columns = ["date", "open", "high", "low", "close", "volume"]
            p["date"] = pd.to_datetime(p["date"]).dt.tz_localize(None).dt.normalize()
            p["ticker"], p["grp"] = tk, grp
            n = nav.reset_index()[["Date", "Close"]]
            n.columns = ["date", "nav"]
            n["date"] = pd.to_datetime(n["date"]).dt.tz_localize(None).dt.normalize()
            n["ticker"] = tk
            p, n = drop_empty(tk, p, n)
            rows.append(p); navs.append(n)
            adv = (p.close * p.volume).tail(21).mean()
            meta.append(dict(ticker=tk, grp=grp, n_px=len(p), n_nav=len(n),
                             start=p.date.min().date(), adv_musd=adv / 1e6,
                             last=p.close.iloc[-1]))
            print(f"  OK  {tk:<6} {grp:<6} px={len(p):>5,} nav={len(n):>5,} "
                  f"from {p.date.min().date()}  ADV ${adv/1e6:>6.1f}M")
    if not rows:
        print("nothing staged"); return 1
    P = pd.concat(rows, ignore_index=True)
    N = pd.concat(navs, ignore_index=True)
    atomic_write(P, OUT / "cef_prices.parquet")
    atomic_write(N, OUT / "cef_nav.parquet")
    M = pd.DataFrame(meta).sort_values("adv_musd", ascending=False)
    atomic_write(M, OUT / "cef_universe.csv")
    print(f"\n  staged {len(M)} credit CEFs, {len(P):,} price rows, {len(N):,} NAV rows")
    print(f"  tradable at $640k (ADV > $3M): {(M.adv_musd > 3).sum()}")
    print(f"  wrote {OUT}/cef_prices.parquet, cef_nav.parquet, cef_universe.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
