"""Listed mandatory convertibles at Alpaca: census, liquidity, shortability, hedged vol.

    export QUANTT_ENV_FILE=<absolute path to the env file holding the Alpaca keys>
    python3 scripts/events/mandatory_census.py              # bars cached under results/events/_cache_mand/
    python3 scripts/events/mandatory_census.py --refresh

WHAT THIS RE-RUNS (plan item 0.9, gate G4)
------------------------------------------
`results/cef/SCALING_RESEARCH_2026-10-08.md` §7.1 row 5: "24 listed, 12 clear
the volume floor, 7 are both liquid and shortable. Hedged residual vol 6–14%.
Cheapness is unmeasured." A desk agent measured these on 2026-10-08/09 in
scratch code, now deleted. Its code survives in the session transcript; this
rebuilds it:

1. **Census.** `GET /v2/assets?status=active&asset_class=us_equity` (read-only),
   classified by NAME with the agent's regex. One fix: the agent's regex missed
   "Mandatorily Convertible" (NFEGP) and patched it by symbol. Here the regex
   matches it, so no symbol is special-cased.
2. **Liquidity.** Daily SIP bars (raw) for every tradable match.
   - The agent's statistic, for reproduction: the MEDIAN of close x volume over
     2026-07-01..2026-10-07, against the frozen spec's `min_adv_usd` (read
     through `scripts/cef/spec.py`, never the literal).
   - The house statistic beside it: the sleeve's own ADV rule
     (`src/deploy/sleeves/cef_discount.py`): the MEAN of close x volume,
     `rolling(63, min_periods=21).mean().shift(1)`, read on the last completed
     session (so it averages the 63 sessions before it). A symbol with fewer
     than 21 prior bars has no ADV and is counted as NOT clearing here.
3. **Shortability** is today's flag (`shortable`, `easy_to_borrow`) from the same
   GET. It is true on its date only (CLAUDE.md landmine 5). The agent's
   2026-10-08 flags are quoted in the note for comparison, not re-derived.
4. **Hedged residual volatility.** For the four pre-2023 mandatories the agent
   probed (DHR.PRA, DHR.PRB, BDXB, AVTR.PRA), weekly (W-FRI) returns of the
   mandatory are regressed on its common, 2019-01-01..2022-12-30. Residual
   s.d. x sqrt(52). The agent used raw closes, so the quarterly dividend drops
   (about 1.2-1.6% a quarter) sit in the mandatory's returns. The
   dividend-adjusted bars (`adjustment=all`) are run beside it as a check. These
   are structure, not P&L: no mean, no Sharpe.
5. **G4 census of 2016-22 listed mandatories with history.** CRSP holds none
   (checked 2026-10-11: no mandatory, unit or preferred share class in
   `dsenames` 2016-22). So the census uses Alpaca's own lists: the
   mandatory-named assets in `status=active` and `status=inactive`, each with its
   SIP bars over 2016-01-01..2022-12-30. **This is a lower bound.** Alpaca's
   inactive list is incomplete: DHR.PRB and BDXB have bars but are not on it.
   The full census needs EDGAR 424B filings, which wait on the team lead's SEC
   user-agent (plan 0.7).

ZERO TRIALS. Read-only GETs; nothing is placed, replaced or cancelled. No
return statistic touches 2023 or later: the residual-vol window ends
2022-12-30, and the liquidity window is volume, not return.

CREDENTIALS: `AlpacaClient.from_environment("cef")` reads the file named by
QUANTT_ENV_FILE. Keys are never printed (the client scrubs them from errors).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("compute.use_numexpr", False)     # scripts/events/numexpr_fault.py

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "cef"))

CACHE = REPO / "results" / "events" / "_cache_mand"                # gitignored
OUT_DIR = REPO / "results" / "events"
MANDATORY_DIR = OUT_DIR / "mandatory"       # the census's outputs: its notes sit in OUT_DIR, its data here

AGENT_WINDOW = ("2026-07-01", "2026-10-07")      # the agent's liquidity window
HEDGE_PAIRS = [("DHR.PRA", "DHR"), ("DHR.PRB", "DHR"), ("BDXB", "BDX"), ("AVTR.PRA", "AVTR")]
HEDGE_WINDOW = ("2019-01-01", "2022-12-30")
CENSUS_WINDOW = ("2016-01-01", "2022-12-30")
HOLDOUT_START = "2023-01-01"
SLEEVE_ADV_DAYS = 63
MANDATORY_MAX_LIFE_YEARS = 3.5   # a flag threshold for ticker reuse, not a fitted number


# --------------------------------------------------------------- classify

_CONV = re.compile(r"CONVERTIB|\bCONV\b|\bCNV\b|\bCV PFD|MANDATORY|MANDATORIL|EQUITY UNIT|CORPORATE UNIT|TANGIBLE EQUITY")
_MAND = re.compile(r"MANDATORY|MANDATORIL|EQUITY UNIT|CORPORATE UNIT|TANGIBLE EQUITY")


def classify(name: str) -> str | None:
    """The agent's name rules (classify_conv_prefs.py, 2026-10-08), with
    'MANDATORIL' added so 'Mandatorily Convertible' is a mandatory."""
    u = name.upper()
    if not _CONV.search(u):
        return None
    if re.search(r"\bETF\b|FUND\b|FUND,|FUND INC|INCOME FUND|TRUST ETF", u) and not _MAND.search(u):
        return "fund_or_etf"
    if re.search(r"RIGHTS?\b", u) and "PREFERRED" not in u:
        return "spac_right"
    if re.search(r"NOTES?\b|DEBENTURE", u) and "PREFERRED" not in u:
        return "listed_conv_note"
    if _MAND.search(u):
        return "mandatory"
    if re.search(r"PREFERRED|PFD|PERP", u):
        return "optional_conv_pref"
    return "other"


# ---------------------------------------------------------------- Alpaca

def _client():
    from quantt.broker.alpaca import AlpacaClient
    return AlpacaClient.from_environment("cef")


def fetch_assets(c, status: str) -> list[dict]:
    from quantt.broker.alpaca import PAPER_BASE
    j = c._get(PAPER_BASE, "/v2/assets", {"status": status, "asset_class": "us_equity"})
    if not isinstance(j, list) or not j:
        raise RuntimeError(f"GET /v2/assets?status={status} returned no list")
    return j


def fetch_bars(c, symbols: list[str], start: str, end: str, adjustment: str, refresh: bool) -> pd.DataFrame:
    """Daily SIP bars, one symbol per request, paginated; cached by (symbol, window, adjustment)."""
    from quantt.broker.alpaca import DATA_BASE, MAX_PAGES
    CACHE.mkdir(parents=True, exist_ok=True)
    out = []
    for sym in symbols:
        p = CACHE / f"bars_{sym.replace('.', '_')}_{start}_{end}_{adjustment}.parquet"
        if p.exists() and not refresh:
            out.append(pd.read_parquet(p))
            continue
        rows, tok = [], None
        for _ in range(MAX_PAGES):
            params = {"symbols": sym, "timeframe": "1Day", "start": start, "end": end,
                      "adjustment": adjustment, "feed": "sip", "limit": 10000}
            if tok:
                params["page_token"] = tok
            j = c._get(DATA_BASE, "/v2/stocks/bars", params)
            for b in (j.get("bars") or {}).get(sym, []) or []:
                rows.append({"symbol": sym, "t": b["t"], "c": float(b["c"]), "v": float(b["v"])})
            tok = j.get("next_page_token")
            if not tok:
                break
        else:
            raise RuntimeError(f"bars for {sym}: pagination did not end")
        df = pd.DataFrame(rows, columns=["symbol", "t", "c", "v"])
        df["date"] = (pd.to_datetime(df["t"], utc=True).dt.tz_convert("America/New_York")
                      .dt.tz_localize(None).dt.normalize())
        df.to_parquet(p, index=False)
        out.append(df)
    out = [d for d in out if not d.empty]        # a symbol with no bar adds no row, and is counted by the caller
    if not out:
        return pd.DataFrame({"symbol": pd.Series(dtype=str), "t": pd.Series(dtype=str), "c": pd.Series(dtype=float),
                             "v": pd.Series(dtype=float), "date": pd.Series(dtype="datetime64[ns]")})
    return pd.concat(out, ignore_index=True)


# ------------------------------------------------------------------ parts

def census(active: list[dict], inactive: list[dict], asof: str) -> pd.DataFrame:
    rows = []
    for status, lst in (("active", active), ("inactive", inactive)):
        for a in lst:
            k = classify(a["name"])
            if k is None:
                continue
            rows.append({"symbol": a["symbol"], "status": status, "kind": k, "exchange": a["exchange"],
                         "tradable": bool(a["tradable"]), "shortable": bool(a["shortable"]),
                         "easy_to_borrow": bool(a["easy_to_borrow"]), "borrow_status": a.get("borrow_status"),
                         "name": a["name"]})
    df = pd.DataFrame(rows).sort_values(["status", "kind", "symbol"]).reset_index(drop=True)
    df.insert(0, "asof", asof)
    return df


def liquidity(c, cen: pd.DataFrame, last_session: str, refresh: bool) -> pd.DataFrame:
    from spec import MIN_ADV_USD
    act = cen[(cen.status == "active") & cen.tradable & cen.kind.isin(["mandatory", "optional_conv_pref", "listed_conv_note"])]
    syms = act.symbol.tolist()
    b1 = fetch_bars(c, syms, AGENT_WINDOW[0], AGENT_WINDOW[1], "raw", refresh)
    start2 = (pd.Timestamp(last_session) - pd.Timedelta(days=130)).strftime("%Y-%m-%d")
    b2 = fetch_bars(c, syms, start2, last_session, "raw", refresh)
    g1 = b1.assign(dv=b1.c * b1.v).groupby("symbol").agg(med_dv_agentwin=("dv", "median"), bars_agentwin=("dv", "size"))
    b2 = b2.assign(dv=b2.c * b2.v).sort_values(["symbol", "date"])
    g2 = b2.groupby("symbol").apply(lambda x: pd.Series({
        "adv63_mean_now": x.dv.rolling(SLEEVE_ADV_DAYS, min_periods=21).mean().shift(1).iloc[-1],
        "bars_63": min(len(x) - 1, SLEEVE_ADV_DAYS), "last_bar": x.date.max()}), include_groups=False)
    if (g2["last_bar"] != pd.Timestamp(last_session)).any():
        stale = g2[g2["last_bar"] != pd.Timestamp(last_session)].index.tolist()
        print(f"   note: last bar is not {last_session} for {stale}; their ADV is read on their own last bar")
    L = act.set_index("symbol")[["kind", "shortable", "easy_to_borrow"]].join(g1).join(g2)
    L["floor_usd"] = MIN_ADV_USD
    L["clears_agent"] = L.med_dv_agentwin >= MIN_ADV_USD
    L["clears_sleeve_def"] = L.adv63_mean_now >= MIN_ADV_USD      # NaN (under 21 bars) compares False
    return L.sort_values("med_dv_agentwin", ascending=False)


def hedged_vol(c, refresh: bool) -> pd.DataFrame:
    syms = sorted({s for pair in HEDGE_PAIRS for s in pair})
    out = []
    for adj in ("raw", "all"):
        b = fetch_bars(c, syms, HEDGE_WINDOW[0], HEDGE_WINDOW[1], adj, refresh)
        if b.date.max() >= pd.Timestamp(HOLDOUT_START):
            raise RuntimeError("a bar on or after 2023-01-01 was read: the time holdout is sealed")
        P = b.pivot(index="date", columns="symbol", values="c")
        for m, cm in HEDGE_PAIRS:
            w = P[[m, cm]].dropna().resample("W-FRI").last().pct_change().dropna()
            beta = float(np.polyfit(w[cm].to_numpy(), w[m].to_numpy(), 1)[0])
            res = w[m].to_numpy() - beta * w[cm].to_numpy()
            out.append({"adjustment": adj, "mandatory": m, "common": cm, "weeks": len(w),
                        "first": P[m].dropna().index.min().date(), "last": P[m].dropna().index.max().date(),
                        "beta": beta, "corr": float(np.corrcoef(w[m], w[cm])[0, 1]),
                        "vol_mand_pct": 100 * w[m].std() * np.sqrt(52), "vol_common_pct": 100 * w[cm].std() * np.sqrt(52),
                        "resid_vol_pct": 100 * res.std(ddof=1) * np.sqrt(52)})
    return pd.DataFrame(out)


def g4_history(c, cen: pd.DataFrame, refresh: bool) -> pd.DataFrame:
    mand = cen[cen.kind == "mandatory"].drop_duplicates("symbol")
    b = fetch_bars(c, mand.symbol.tolist(), CENSUS_WINDOW[0], CENSUS_WINDOW[1], "raw", refresh)
    if not b.empty and b.date.max() >= pd.Timestamp(HOLDOUT_START):
        raise RuntimeError("a bar on or after 2023-01-01 was read")
    h = b.groupby("symbol").agg(first_bar=("date", "min"), last_bar=("date", "max"), bars=("date", "size"))
    out = mand.set_index("symbol")[["status", "name"]].join(h)
    out["bars"] = out["bars"].fillna(0).astype(int)      # no bar returned = zero bars, a count not a guess
    # A mandatory lives about three years. Bars spanning much longer mean the
    # symbol carried another security too (ticker reuse); flagged, not resolved.
    span = (out["last_bar"] - out["first_bar"]).dt.days / 365.25
    out["span_years"] = span.round(2)
    out["suspect_reuse"] = span > MANDATORY_MAX_LIFE_YEARS
    return out.sort_values("first_bar")


# ------------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="re-fetch bars (the asset lists are always fetched)")
    args = ap.parse_args(argv)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 60)
    c = _client()
    clock = c.clock()
    asof = pd.Timestamp(clock["timestamp"]).tz_convert("America/New_York")
    # Last COMPLETED session: a calendar day before today, or today once the
    # market has closed (is_open false and past 17:00 ET, after the close).
    cal = c.calendar(asof.date() - dt.timedelta(days=10), asof.date())
    done = [d["date"] for d in cal if d["date"] < asof.date()
            or (d["date"] == asof.date() and not clock["is_open"] and asof.hour >= 17)]
    if not done:
        raise RuntimeError("no completed session in the last 10 calendar days")
    last_session = max(done).isoformat()
    print(f"Alpaca clock {asof.isoformat()} ET; last completed session {last_session}")

    active, inactive = fetch_assets(c, "active"), fetch_assets(c, "inactive")
    cen = census(active, inactive, asof.strftime("%Y-%m-%d"))
    MANDATORY_DIR.mkdir(parents=True, exist_ok=True)
    snap = MANDATORY_DIR / f"alpaca_convertible_assets_{asof.strftime('%Y-%m-%d')}.csv"
    cen.to_csv(snap, index=False)
    meta = {"asof_et": asof.isoformat(), "endpoint": "GET /v2/assets?asset_class=us_equity (paper, cef key)",
            "n_active": len(active), "n_inactive": len(inactive), "n_convertible_named": len(cen)}
    (MANDATORY_DIR / f"alpaca_convertible_assets_{asof.strftime('%Y-%m-%d')}.meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"assets: active {len(active)}, inactive {len(inactive)}; convertible-named rows written to {snap.relative_to(REPO)}")
    act = cen[cen.status == "active"]
    print("\n== census, active list, flags as of", asof.date())
    print(act.groupby("kind").agg(n=("symbol", "size"), tradable=("tradable", "sum"), shortable=("shortable", "sum"),
                                  etb=("easy_to_borrow", "sum")).to_string())

    L = liquidity(c, cen, last_session, args.refresh)
    print(f"\n== liquidity: agent's statistic (median daily $ volume, {AGENT_WINDOW[0]}..{AGENT_WINDOW[1]}) and the "
          f"sleeve's (63-session mean to {last_session}); floor = spec min_adv_usd")
    show = L.assign(med_m=(L.med_dv_agentwin / 1e6).round(2), adv63_m=(L.adv63_mean_now / 1e6).round(2))
    print(show[["kind", "shortable", "easy_to_borrow", "bars_agentwin", "med_m", "clears_agent", "bars_63", "adv63_m",
                "clears_sleeve_def"]].to_string())
    for k in ("mandatory", "optional_conv_pref", "listed_conv_note"):
        x = L[L.kind == k]
        print(f"   {k:<19} n {len(x):>2} | agent stat: clear {int(x.clears_agent.sum())}, clear & shortable today "
              f"{int((x.clears_agent & x.shortable).sum())} | sleeve def: clear {int(x.clears_sleeve_def.sum())}, "
              f"clear & shortable today {int((x.clears_sleeve_def & x.shortable).sum())} | shortable today {int(x.shortable.sum())}")

    H = hedged_vol(c, args.refresh)
    print(f"\n== hedged residual vol, weekly, {HEDGE_WINDOW[0]}..{HEDGE_WINDOW[1]} (structure only: no mean, no Sharpe)")
    print(H.round(2).to_string(index=False))

    G = g4_history(c, cen, args.refresh)
    print(f"\n== G4: mandatory-named symbols on Alpaca's active + inactive lists, SIP bars {CENSUS_WINDOW[0]}..{CENSUS_WINDOW[1]}")
    print(G.assign(name=G.name.str[:60]).to_string())
    have = G[G.bars > 0]
    clean = have[~have.suspect_reuse]
    print(f"   with any bar in the window: {len(have)}; with >= 250 bars: {int((G.bars >= 250).sum())}; "
          f"of which span <= {MANDATORY_MAX_LIFE_YEARS} years (no suspected ticker reuse): {len(clean)}; "
          f"of {len(G)} mandatory-named symbols on the lists")
    probed = [m for m, _ in HEDGE_PAIRS if m not in set(G.index)]
    print(f"   agent-probed pre-2023 mandatories NOT on either list but with bars: {probed}")
    G.reset_index().to_csv(MANDATORY_DIR / "mandatory_g4_history.csv", index=False)
    L.reset_index().to_csv(MANDATORY_DIR / "mandatory_liquidity.csv", index=False)
    H.to_csv(MANDATORY_DIR / "mandatory_hedged_vol.csv", index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
