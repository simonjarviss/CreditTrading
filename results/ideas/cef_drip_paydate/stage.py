"""Stage the inputs of the pay-date (reinvestment-plan) test. Rows go OUTSIDE the repository.

    QUANTT_ENV_FILE=<env file> python3 results/ideas/cef_drip_paydate/stage.py r2      # CRSP on R2
    python3 results/ideas/cef_drip_paydate/stage.py yahoo                               # NAVs, live funds

WHY TWO STEPS. The staged CEF panel (scripts/research/stage_crsp_cefs.py) carries prices,
returns and ex-date amounts, but not the PAYMENT date, the declaration date, the closing
quotes or shares outstanding; `r2` pulls those for the same funds (every closed-end fund CRSP
ever listed, dead ones included). CRSP has no net asset value, and the discount is the sharp
split of this idea (a plan agent buys in the market only when the fund trades below NAV), so
`yahoo` fetches the daily NAV series Yahoo Finance serves under X<TICKER>X for funds still
listed on the CRSP panel's last date and not already in the desk's own NAV panels.

WHAT THIS CANNOT GIVE: a NAV for a fund that has since been liquidated or merged. Any split
on the discount is therefore on SURVIVORS, and explore.py shows the price-only result on all
funds beside it. A ticker Yahoo does not serve is logged as missing; nothing is filled.

Licensed rows (CRSP) and fetched rows (Yahoo) are written under ~/quantt_research/cef_drip_paydate/.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
ROOT = Path.home() / "quantt_research"
OUT = ROOT / "cef_drip_paydate"
PANEL = ROOT / "crsp_cef_daily.parquet"
# The desk's NAV panels live in the MAIN checkout's data/ (gitignored, so absent from a worktree). Read-only.
DESK_DATA = Path("/Users/simonjarvis/Downloads/2027/Projects/Quant - PM2027/2027/data")
DESK_NAV = (DESK_DATA / "cef" / "cef_nav.parquet", DESK_DATA / "cef_families" / "cef_nav.parquet")


def _opens(f: Path) -> bool:
    """RESUME (2026-11-18): the first run was killed while DuckDB was writing the quotes file, which
    was left at 0 bytes. A parquet has its footer written last, so a file that opens is complete;
    one that does not is rebuilt, never trusted."""
    try:
        return f.exists() and f.stat().st_size > 0 and len(pd.read_parquet(f, columns=["permno"])) > 0
    except Exception as e:                  # not a fallback: the file is rebuilt from the source
        print(f.name, "does not open, rebuilding:", repr(e)[:80]); return False


def stage_r2() -> None:
    from src.data import r2
    con = r2.connect()
    con.execute(f"create table cef as select distinct permno from read_parquet('{PANEL}')")
    if not _opens(OUT / 'stkdist_cef_raw.parquet'):
      con.execute(f"""copy (select d.* from read_parquet('{r2.r2_path('crsp_a_stock', 'stkdistributions')}') d
                          join cef using (permno) where disexdt >= date '1999-06-01' order by permno, disexdt)
                    to '{OUT / 'stkdist_cef_raw.parquet'}' (format parquet, compression zstd)""")
    if not _opens(OUT / 'crsp_cef_quotes.parquet'):
      con.execute(f"""copy (select permno, dlycaldt as date, cast(dlybid as double) bid, cast(dlyask as double) ask,
                                 cast(dlyvol as double) vol, cast(shrout as double) shrout
                          from read_parquet('{r2.r2_path('crsp_a_stock', 'dsf_v2')}')
                          where dlycaldt >= date '2000-01-01' and securitysubtype = 'CEF'
                            and conditionaltype = 'RW' and tradingstatusflg = 'A' order by date, permno)
                    to '{OUT / 'crsp_cef_quotes.parquet'}' (format parquet, compression zstd)""")
    for f in ("stkdist_cef_raw.parquet", "crsp_cef_quotes.parquet"):
        print(f, len(pd.read_parquet(OUT / f)), "rows")


def stage_yahoo() -> None:
    import yfinance as yf
    df = pd.read_parquet(PANEL, columns=["permno", "ticker", "date"])
    live = df[df["date"] == df["date"].max()].dropna(subset=["ticker"])
    have = set()
    for f in DESK_NAV:
        have |= set(pd.read_parquet(f, columns=["ticker"])["ticker"].unique())
    want = sorted(set(live["ticker"]) - have)
    cache = OUT / "yahoo_nav"
    cache.mkdir(parents=True, exist_ok=True)
    log = []
    for i, t in enumerate(want):
        dest = cache / f"{t}.parquet"
        if dest.exists():
            try:                            # a file half-written at the kill is refetched
                log.append((t, "cached", len(pd.read_parquet(dest)))); continue
            except Exception:
                dest.unlink()
        sym = f"X{t}X"
        try:
            h = yf.download(sym, start="2000-01-01", end="2026-01-01", auto_adjust=False, progress=False, threads=False)
        except Exception as e:              # logged as missing below, never filled
            h = pd.DataFrame(); err = repr(e)[:80]
        else:
            err = "empty"
        if h is None or h.empty:
            log.append((t, f"missing: {err}", 0))
        else:
            c = h["Close"]
            c = c.iloc[:, 0] if isinstance(c, pd.DataFrame) else c
            s = c.dropna().rename("nav").rename_axis("date").reset_index()
            s["date"] = pd.to_datetime(s["date"]).dt.tz_localize(None)
            s["ticker"] = t
            s.to_parquet(dest)
            log.append((t, "fetched", len(s)))
        time.sleep(1.0)
        if i % 25 == 24:
            print(i + 1, "of", len(want), flush=True); time.sleep(5)
    lg = pd.DataFrame(log, columns=["ticker", "status", "rows"])
    lg.to_csv(OUT / "yahoo_nav_log.csv", index=False)
    print(len(want), "live funds without a desk NAV;", int((lg["rows"] > 0).sum()), "have a Yahoo NAV series;",
          int((lg["rows"] == 0).sum()), "missing")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    if REPO.resolve() in OUT.resolve().parents:
        raise SystemExit("refusing: rows stay outside the repository")
    {"r2": stage_r2, "yahoo": stage_yahoo}[sys.argv[1]]()
