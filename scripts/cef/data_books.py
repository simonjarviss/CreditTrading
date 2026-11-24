"""Which panels a nightly fetcher writes, per book: the core's and C4's (plan step 3, DARK).

    python3 scripts/cef/data_books.py nav-map --check      # the committed C4 NAV-symbol map still derives
    python3 scripts/cef/data_books.py nav-map --write      # re-derive it (data/cef_families/, read-only)
    python3 scripts/cef/data_books.py seed-c4 --from data/cef_families --out DIR   # SEED below; NOT RUN

WHY THIS EXISTS (C4 deployment plan, step 3; team lead's fast-track, 2026-10-28)
-------------------------------------------------------------------------------
`results/cef/C4_DEPLOY_PLAN_2026-10-27.md` §1 row 3 gives C4 its own nightly
data path: prices, NAVs and distributions for the 74 frozen funds, in their own
directory, under their own lock. Three programs need the same answers to "which
directory, which funds, which NAV symbol, may CEFConnect be read": the price and
NAV refresh (`scripts/cef/fetch_daily.py --data-book c4`), the distribution
fetcher (`scripts/fetch_cef_distributions.py --data-book c4`) and the collector
(`quantt/collect/collect.py`, `BOOKS["c4"]`). Written once here, so they cannot
disagree. This module imports only the standard library at module level: the
collector imports it inside `build_ctx`, and the session must never load
yfinance by way of it (quantt/session/nav_gate.py, PanelGate).

THE CORE IS NOT HERE. With no book named, or "cef", every fetcher does what it
did at 29e5dc0, byte for byte, from its own module constants (data/cef/, the
panel's own tickers, X<TK>X, CEFConnect allowed). Nothing in this file is read
on that path except the name `CefConnectDisabled`, which the core never raises.

THE C4 BOOK
-----------
* Directory `data/cef_c4/`: `cef_prices.parquet`, `cef_nav.parquet` (the live
  schema, so the sleeve's `panel_source` reads them unchanged: C4 step 1,
  quantt/session/tests/test_c4_keys_noop.py), `cef_distributions.parquet`,
  `cef_splits.parquet`, `alpaca_official_close.parquet` (the collector's).
* Lock `data/cef_c4/.fetch.lock`, not the core's `data/cef/.fetch.lock`: the
  core's session and collector, and C4's collector, refresh different files, and
  a 74-name fetch must never make the 13's refresh wait toward its cls cutoff.
* Funds: the 74 the team lead froze on 2026-10-14
  (`results/cef/c4/c4_universe_frozen_2026-10-14.csv`; PREREG_C4 amendment).
  Disjoint from the core's 44 [V, the plan's §0]. When step 2's frozen spec
  lands, its universe must equal this list (a test there, not here).
* NAV symbol: CEFConnect's `NavTicker`, not `X<TK>X`, for 15 of the 74, and none
  named for EVT (16 of 74 differ from `X<TK>X`; data/cef_families/universe.csv
  [V 2026-10-29]). The map is `results/cef/c4/c4_nav_symbols_2026-10-14.csv`,
  derived by `build_c4_nav_map` below by the rule the families panels were BUILT
  with (`scripts/data/fetch_cef_families_yf.py` `nav_candidates`: CEFConnect's
  symbol, else `X<TK>X`), and checked against the symbol that build actually
  used (`data/cef_families/yf_fetch_log.csv` `nav_symbol`): all 74 agree. So the
  nightly NAV continues the series the trial ran on. EVT's `XEVTX` is that
  build's own measured series, not a default. The map is committed because prod
  has no `data/cef_families/` (it is never seeded there), and `--check` re-derives
  it wherever that directory exists.
* CEFConnect: DISABLED (the team lead's §3 ruling 3, accepted 2026-10-28: "none
  for C4"; CEFConnect's terms, docs/REFERENCES.md §12y). A C4 fetch refuses
  `--nav-fallback cefconnect`, and the collector's C4 reader raises
  `CefConnectDisabled`. Stale NAVs are C4's NAV-repeat mask M1's to catch
  (`cef_discount` `nav_repeat_mask`, step 1), not a second source's.

SEED (documented 2026-10-29; NOT RUN -- the team lead runs it, at the installer step)
-----------------------------------------------------------------------------------
Prod's `data/cef_c4/` starts from the families history the trial ran on, plus
one fetch. The families panels exist only on the laptop's dev tree. Three steps:

  1. Laptop, the dev tree at the release tag, read-only on `data/`:
         python3 scripts/cef/data_books.py seed-c4 --from data/cef_families --out ~/c4_seed
     It keeps the 74 (every one must have price and NAV rows), checks the live
     schema, the families against the frozen file, no duplicate (date, ticker),
     no row without a close or a NAV (`fetch_daily.has_close`/`has_nav`), no
     name of `data/cef/cef_universe.csv`, and runs `data_guards.guard_closes`
     over the whole history. It writes `cef_prices.parquet`, `cef_nav.parquet`
     and `seed_manifest.json` (sha256, rows, dates, what the guard found) to
     `--out`, which may not be inside `data/` and may not already hold a seed.
     EXPECTED TO REFUSE on today's panel: IGR's four post-split-basis bars,
     2026-07-29 .. 08-11 (results/cef/data_guards/scan_output_2026-10-19.txt
     [V]). Whether to seed with a ruling (`--bar-rulings FILE`; C4's research
     ruling is results/cef/c4/c4_bar_rulings_2026-10-19.json, `rebase`) is the
     team lead's decision. Those bars are inside the first fetch's window, so
     step 3 re-fetches them and judges them again either way.
  2. The installer step copies the two panels into prod's `data/cef_c4/` only
     where absent, checking each sha256 against the manifest (as install_vm
     does for `data/cef`, SEED_FILES).
  3. Prod, as the service user:
         python3 scripts/cef/fetch_daily.py --data-book c4
         python3 scripts/fetch_cef_distributions.py --data-book c4
     The first appends 2026-10-12 onward (the families panel ends 2026-10-09)
     and exits 0, or 6 if a split-like bar in the fetched window has no ruling
     (fetch_daily, C4 BOOK). The default `--period 6mo` reaches back past the
     seed's last date until 2027-04-09; after that, pass `--period 1y`.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:            # run as a script, not -m
    sys.path.insert(0, str(REPO))

CORE, C4 = "cef", "c4"
BOOK_NAMES = (C4, CORE)
C4_DIR = REPO / "data" / "cef_c4"
C4_UNIVERSE = REPO / "results" / "cef" / "c4" / "c4_universe_frozen_2026-10-14.csv"
C4_NAV_MAP = REPO / "results" / "cef" / "c4" / "c4_nav_symbols_2026-10-14.csv"
C4_N = 74                                 # the team lead's frozen read of 2026-10-14
# THE PRICE BASIS (2026-11-04): the live fetch's split rulings (data_guards.py, THE LIVE
# FETCH'S PRICE BASIS), read by fetch_daily --data-book c4 and `repair-basis`.
C4_FETCH_SPLIT_RULINGS = REPO / "results" / "cef" / "c4" / "c4_fetch_split_rulings_2026-11-03.json"
# How far back a nightly fetch can have written (its period, 6mo, plus slack): the rows
# `repair-basis` judges, so a fund's discount years ago never decides tonight's basis.
REPAIR_WINDOW_DAYS = 220
REPAIR_LOG = "basis_repair_log.csv"
FAMILIES_DIR = REPO / "data" / "cef_families"
NAV_MAP_COLUMNS = ("ticker", "nav_symbol", "source", "nav_ticker_cefconnect",
                   "families_nav_symbol", "families_nav_status")
PX_COLUMNS = ["date", "open", "high", "low", "close", "volume", "ticker", "grp"]
NAV_COLUMNS = ["date", "nav", "ticker"]
SEED_FILES = ("cef_prices.parquet", "cef_nav.parquet")
SEED_MANIFEST = "seed_manifest.json"


class DataBookError(RuntimeError):
    """A data book's configuration or panel is not what it must be; names what is wrong."""


class CefConnectDisabled(RuntimeError):
    """A book whose CEFConnect use is disabled was asked to read it (C4: team lead, 2026-10-28)."""


def refuse_cefconnect(book: str):
    """A CEFConnect reader for a book that may not read it: every call raises."""
    def refused(*args, **kwargs):
        raise CefConnectDisabled(
            f"CEFConnect is disabled for data book {book!r} (team lead's ruling, "
            f"C4_DEPLOY_PLAN_2026-10-27.md §3 item 3, accepted 2026-10-28); C4's NAV-repeat "
            f"mask M1 catches a stale NAV instead")
    return refused


def _rows(path: Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise DataBookError(f"{p} does not exist")
    with open(p, newline="") as fh:
        return list(csv.DictReader(fh))


def c4_universe(path: Path | None = None) -> dict:
    """{ticker: family} for the 74 frozen funds, read from the tracked frozen file.

    Raises unless it holds exactly C4_N distinct tickers, each with a family:
    the frozen set is the definition of the book, so a file that has drifted is
    refused rather than fetched."""
    p = C4_UNIVERSE if path is None else Path(path)
    rows = _rows(p)
    out = {}
    for r in rows:
        t, f = (r.get("ticker") or "").strip(), (r.get("family") or "").strip()
        if not t or not f:
            raise DataBookError(f"{p.name}: a row has no ticker or no family: {r}")
        if t in out:
            raise DataBookError(f"{p.name}: {t} is listed twice")
        out[t] = f
    if len(out) != C4_N:
        raise DataBookError(f"{p.name} holds {len(out)} funds; the frozen C4 universe is {C4_N}")
    return out


def c4_nav_symbols(path: Path | None = None, universe: dict | None = None) -> dict:
    """{ticker: yfinance NAV symbol} for the 74, from the committed map.

    Refuses a map that does not cover exactly the frozen universe, lists a
    ticker twice, names an empty symbol, names the price ticker itself (a
    price is not a NAV), or gives two funds one symbol."""
    p = C4_NAV_MAP if path is None else Path(path)
    uni = c4_universe() if universe is None else universe
    rows = _rows(p)
    if rows and tuple(rows[0]) != NAV_MAP_COLUMNS:
        raise DataBookError(f"{p.name} has columns {list(rows[0])}, expected {list(NAV_MAP_COLUMNS)}")
    out = {}
    for r in rows:
        t, s = r["ticker"].strip(), r["nav_symbol"].strip()
        if t in out:
            raise DataBookError(f"{p.name}: {t} is listed twice")
        if not s or s == t:
            raise DataBookError(f"{p.name}: {t}'s NAV symbol {s!r} is empty or is the price ticker")
        out[t] = s
    if set(out) != set(uni):
        raise DataBookError(f"{p.name} does not cover the frozen universe: missing "
                            f"{sorted(set(uni) - set(out))}, extra {sorted(set(out) - set(uni))}")
    dup = sorted({s for s in out.values() if list(out.values()).count(s) > 1})
    if dup:
        raise DataBookError(f"{p.name}: NAV symbol(s) {dup} are named for more than one fund")
    return out


# --------------------------------------------------------------------------- the NAV-symbol map

def build_c4_nav_map(universe_csv: Path, fetch_log_csv: Path, frozen_csv: Path | None = None) -> list[dict]:
    """The map's rows, derived (never hand-copied) from the families build's own inputs.

    For each frozen fund: the symbol the families fetcher would try FIRST
    (`fetch_cef_families_yf.nav_candidates`: CEFConnect's `NavTicker`, else
    `X<TK>X`), which must equal the symbol that build actually used for the
    panel (`yf_fetch_log.csv` `nav_symbol`). A fund the families build gave no
    NAV, or a disagreement, raises naming it: the nightly series must continue
    the one the trial ran on, and a symbol chosen any other way would not."""
    from scripts.data.fetch_cef_families_yf import nav_candidates
    uni = c4_universe(frozen_csv)
    u = {r["ticker"]: r for r in _rows(universe_csv)}
    log = {r["ticker"]: r for r in _rows(fetch_log_csv)}
    out, bad = [], []
    for t in sorted(uni):
        if t not in u or t not in log:
            bad.append(f"{t}: absent from {'universe.csv' if t not in u else 'yf_fetch_log.csv'}")
            continue
        cc = (u[t].get("nav_ticker_cefconnect") or "").strip()
        rule = nav_candidates(t, cc or None)[0]
        used = (log[t].get("nav_symbol") or "").strip()
        if not used:
            bad.append(f"{t}: the families build has no NAV ({log[t].get('nav_status')})")
            continue
        if used != rule:
            bad.append(f"{t}: the rule gives {rule}, the families panel used {used}")
            continue
        out.append({"ticker": t, "nav_symbol": rule,
                    "source": "cefconnect_nav_ticker" if cc and cc == rule else "x_tk_x",
                    "nav_ticker_cefconnect": cc, "families_nav_symbol": used,
                    "families_nav_status": log[t].get("nav_status", "")})
    if bad:
        raise DataBookError("the C4 NAV-symbol map cannot be derived: " + "; ".join(bad))
    return out


def _map_text(rows: list[dict]) -> str:
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=NAV_MAP_COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


# --------------------------------------------------------------------------- the seed (NOT RUN)

def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seed_c4(src: Path, out: Path, *, rulings: Path | None = None,
            universe: Path | None = None, core_universe: Path | None = None) -> dict:
    """Build the first `data/cef_c4/` panels from the families history (SEED above).

    Writes `cef_prices.parquet`, `cef_nav.parquet` and `seed_manifest.json`
    into `out` and returns the manifest. Every check raises naming what failed;
    nothing is dropped, filled or repaired except a bar a passed rulings file
    treats (`data_guards.guard_closes`, close only, each one listed in the
    manifest). The guard is given no split multipliers: these closes are
    yfinance's, which it back-adjusts for every split it knows, so they are on
    one basis already, and a recorded multiplier would create the very step
    the split-basis guard exists to catch (data_guards.py, guard 3)."""
    import datetime as dt
    import pandas as pd
    from ops.common import atomic_write
    from scripts.cef.data_guards import guard_closes
    from scripts.cef.fetch_daily import has_close, has_nav
    src, out = Path(src), Path(out).resolve()
    data_dir = (REPO / "data").resolve()
    if out == data_dir or data_dir in out.parents:
        raise DataBookError(f"--out {out} is inside {data_dir}: the seed is built beside the live "
                            f"data, and the installer step copies it in (SEED step 2)")
    held = [n for n in SEED_FILES + (SEED_MANIFEST,) if (out / n).exists()]
    if held:
        raise DataBookError(f"{out} already holds {held}; a seed is never written over")
    fam = c4_universe(universe)
    names = sorted(fam)
    core_csv = (REPO / "data" / "cef" / "cef_universe.csv") if core_universe is None else Path(core_universe)
    core = {r["ticker"] for r in _rows(core_csv)}
    if set(names) & core:
        raise DataBookError(f"{sorted(set(names) & core)} are core names ({core_csv}); C4 must not "
                            f"carry one (the 27-name holdout, H9)")
    srcs = {n: src / n for n in SEED_FILES}
    P = pd.read_parquet(srcs["cef_prices.parquet"])
    N = pd.read_parquet(srcs["cef_nav.parquet"])
    if list(P.columns) != PX_COLUMNS or list(N.columns) != NAV_COLUMNS:
        raise DataBookError(f"source columns {list(P.columns)} / {list(N.columns)} are not the live "
                            f"schema {PX_COLUMNS} / {NAV_COLUMNS}")
    P = P[P["ticker"].isin(names)].sort_values(["ticker", "date"]).reset_index(drop=True)
    N = N[N["ticker"].isin(names)].sort_values(["ticker", "date"]).reset_index(drop=True)
    for what, frame in (("price", P), ("NAV", N)):
        miss = sorted(set(names) - set(frame["ticker"]))
        if miss:
            raise DataBookError(f"no {what} rows in {src} for {miss}")
        dup = frame[frame.duplicated(["date", "ticker"], keep=False)]
        if len(dup):
            raise DataBookError(f"duplicate (date, ticker) {what} rows, e.g. {dup.head(3).to_dict('records')}")
    wrong = {t: sorted(map(str, g)) for t, g in P.groupby("ticker")["grp"].unique().items()
             if list(g) != [fam[t]]}
    if wrong:
        raise DataBookError(f"grp is not the frozen family for {wrong}")
    nc, nn = int((~has_close(P)).sum()), int((~has_nav(N)).sum())
    if nc or nn:
        raise DataBookError(f"{nc} price row(s) with no close and {nn} NAV row(s) with no NAV in the "
                            f"seed; the families build drops such rows, so the source has changed")
    close = P.pivot(index="date", columns="ticker", values="close")
    navw = N.pivot(index="date", columns="ticker", values="nav")
    treated, log = guard_closes(close, cols=names, lo=close.index.min(), hi=close.index.max(),
                                nav=navw, splits=None, rulings=rulings, context="seed-c4")
    applied = []
    for r in log.itertuples():
        if r.treatment == "rebase":
            m = (P["ticker"] == r.ticker) & (P["date"] == r.date)
            P.loc[m, "close"] = float(treated.at[r.date, r.ticker])
        applied.append({"ticker": r.ticker, "date": str(pd.Timestamp(r.date).date()),
                        "treatment": r.treatment, "factor": float(r.factor)})
    out.mkdir(parents=True, exist_ok=True)
    atomic_write(P, out / "cef_prices.parquet")
    atomic_write(N, out / "cef_nav.parquet")
    man = {"built_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "what": "first data/cef_c4 panels (scripts/cef/data_books.py, SEED)",
           "universe": {"path": str(Path(universe or C4_UNIVERSE)), "sha256": _sha256(universe or C4_UNIVERSE),
                        "n": len(names)},
           "sources": {n: {"path": str(p), "sha256": _sha256(p)} for n, p in srcs.items()},
           "bar_rulings": None if rulings is None else {"path": str(rulings), "sha256": _sha256(rulings)},
           "treated_closes": applied,
           "files": {n: {"sha256": _sha256(out / n), "rows": int(len(f)),
                         "first": str(f["date"].min().date()), "last": str(f["date"].max().date())}
                     for n, f in (("cef_prices.parquet", P), ("cef_nav.parquet", N))}}
    (out / SEED_MANIFEST).write_text(json.dumps(man, indent=1, sort_keys=True) + "\n")
    return man


# --------------------------------------------------------------------------- REPAIR (THE PRICE BASIS)

def repair_basis(panel_dir: Path | None = None, rulings: Path | None = None, *,
                 lock_wait_s: float = 600.0) -> dict:
    """Put the STORED C4 price rows a past fetch wrote on the vendor's split-adjusted basis
    back on the NAV's basis, under the C4 fetch lock, and log every row changed.

    WHY (2026-11-04). The fetch of 2026-11-03 wrote IGR's 2026-05-04..09-04 closes at x3.0
    (data_guards.py, THE LIVE FETCH'S PRICE BASIS). The fixed fetch puts tonight's fetched
    rows on the NAV's basis and refuses a step against the stored rows, so the stored
    window has to be repaired first, once, or the fixed fetch refuses every night. The
    repair is the fetch's own judgement (`to_nav_basis`, the same rulings file), on the
    stored rows of the last REPAIR_WINDOW_DAYS, judged against the stored NAVs. A row the
    NAV cannot place raises and nothing is written. Idempotent: a second run changes
    nothing and says so. Writes `<panel_dir>/basis_repair_log.csv` (appended) and the price
    panel atomically; the NAV panel is never touched."""
    import datetime as dt
    import pandas as pd
    from ops.common import atomic_write
    from scripts.cef import fetch_daily as fd
    from scripts.cef.data_guards import load_fetch_split_rulings, to_nav_basis
    d = Path(C4_DIR if panel_dir is None else panel_dir)
    rp = Path(C4_FETCH_SPLIT_RULINGS if rulings is None else rulings)
    R = load_fetch_split_rulings(rp)
    px_path, nav_path = d / "cef_prices.parquet", d / "cef_nav.parquet"
    with fd.panel_lock(d / ".fetch.lock", lock_wait_s, 1.0):
        P, N = pd.read_parquet(px_path), pd.read_parquet(nav_path)
        lo = pd.Timestamp(P["date"].max()) - pd.Timedelta(days=REPAIR_WINDOW_DAYS)
        win = P[pd.to_datetime(P["date"]) >= lo]
        fixed, log = to_nav_basis(win, N, R, context=f"repair-basis {d}")
        changed = fixed.index[(fixed["close"] != win["close"]) & win["close"].notna()]
        rows = []
        if len(changed):
            stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            for i in changed:
                rows.append({"repaired_utc": stamp, "ticker": P.at[i, "ticker"],
                             "date": str(pd.Timestamp(P.at[i, "date"]).date()),
                             "close_before": float(P.at[i, "close"]), "close_after": float(fixed.at[i, "close"]),
                             "volume_before": int(P.at[i, "volume"]), "volume_after": int(fixed.at[i, "volume"]),
                             "rulings": rp.name, "rulings_sha256": _sha256(rp)})
            for c in ("open", "high", "low", "close", "volume"):
                P.loc[changed, c] = fixed.loc[changed, c]
            P["volume"] = P["volume"].astype("int64")
            atomic_write(P, px_path)
            lp = d / REPAIR_LOG
            new = not lp.exists()
            with open(lp, "a", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0]))
                if new:
                    w.writeheader()
                w.writerows(rows)
    return {"panel": str(px_path), "rulings": str(rp), "window_from": str(lo.date()),
            "repaired": len(rows),
            "by_ticker": {e["ticker"]: {"converted": e.get("converted", 0), "raw": e.get("raw"),
                                        "first": None if not e.get("first") else str(e["first"].date()),
                                        "last": None if not e.get("last") else str(e["last"].date())}
                          for e in log}}


# --------------------------------------------------------------------------- CLI

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("nav-map", help="derive the C4 NAV-symbol map from data/cef_families/ (read-only)")
    g = m.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="exit 1 unless the committed map re-derives exactly")
    g.add_argument("--write", action="store_true", help="write the committed map")
    m.add_argument("--families", type=Path, default=FAMILIES_DIR)
    s = sub.add_parser("seed-c4", help="build the first data/cef_c4 panels (SEED; the team lead runs it)")
    s.add_argument("--from", dest="src", type=Path, required=True)
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--bar-rulings", type=Path, default=None)
    r = sub.add_parser("repair-basis", help="put stored C4 closes a past fetch wrote split-adjusted "
                                            "back on the NAV's basis (THE PRICE BASIS; the team lead runs it)")
    r.add_argument("--book", choices=[C4], required=True)
    a = ap.parse_args(argv)
    if a.cmd == "repair-basis":
        out = repair_basis()
        print(json.dumps(out, indent=1, sort_keys=True))
        return 0
    if a.cmd == "nav-map":
        text = _map_text(build_c4_nav_map(a.families / "universe.csv", a.families / "yf_fetch_log.csv"))
        if a.write:
            C4_NAV_MAP.write_text(text)
            print(f"wrote {C4_NAV_MAP}")
            return 0
        same = C4_NAV_MAP.exists() and C4_NAV_MAP.read_text() == text
        print(f"{C4_NAV_MAP.name}: {'re-derives exactly' if same else 'DIFFERS from what data/cef_families derives'}")
        return 0 if same else 1
    man = seed_c4(a.src, a.out, rulings=a.bar_rulings)
    print(json.dumps(man, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
