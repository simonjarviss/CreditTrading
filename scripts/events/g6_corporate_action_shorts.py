"""Gate G6: did the live book short funds under a pending NAV tender, merger or liquidation, and what did it cost?

    export QUANTT_ENV_FILE=/abs/path/config/.env
    python3 scripts/events/g6_corporate_action_shorts.py            # -> results/events/g6/g6_*.json|csv
    python3 scripts/events/g6_corporate_action_shorts.py --offline  # EDGAR from the cache only

ZERO TRIALS. REPORT ONLY. `results/cef/RESEARCH_PLAN_2026-10-09.md` §2, G6: "from
0.7: how often the live book held a short in a name under a pending NAV
tender, merger or liquidation, and what that cost". It passes ("build the
filter", trial C1) if the cost is material -- at least the cost grid per year
-- and otherwise the filter is built as hygiene with no trial. Nothing here is
pre-registered and no counter moves. The fit period only: the 2023-01-01 time
holdout is sealed (`fit_only` truncates before any policy runs, and asserts it).

WHY THE QUESTION IS WORTH ASKING
--------------------------------
The book shorts a fund whose discount is narrow relative to its own 252-day
history. A fund whose board has announced a tender at ~98% of NAV, a merger
into a fund at a narrower discount, or a liquidation at NAV has a discount
that is narrow FOR A REASON and is going to stay narrow or close: the z-score
reads that as rich and shorts into a price that is converging up to NAV. That
is adverse selection the signal cannot see. A tender for the fund's PREFERRED
shares (auction-rate preferreds, which several PIMCO funds bought back
2014-24) is a different event: it does not pull the common shares to NAV, so
it is classified apart and not counted as a NAV tender.

WHAT IS MEASURED
----------------
1. **The events**, for the 13 spec names (`scripts/cef/spec.py`), from EDGAR
   (plan 0.7): each fund's complete filing history from the submissions API,
   grouped into episodes by `fetch_edgar_events.episodes`.
   * Tender: an SC TO-I / SC TO-C / SC TO-T episode. The security is read
     from the filing's cover page ("Title of Class of Securities"):
     `classify_tender`. Window: first filing -> last amendment (the final
     amendment reports the result after expiry, so the window ends a few days
     late: conservative toward finding cost).
   * Merger: a 425 / N-14 8C episode. Role "acquirer" if the fund filed the
     N-14 8C; else "target". End: the CRSP completion date (the last
     delisting into this fund; CRSP codes some reorganisations 331, not 231,
     so both are read), else the episode's last filing.
   * Liquidation / open-ending: no form says so. Every PRE 14A / PRER14A and
     8-K the fund filed is read and searched for a liquidation, termination or
     open-end-conversion proposal (`scan_proxy`). A hit is printed for a
     reader; a hit that is a proposal becomes a window.
   * Proxy contests (PREC14A, DFAN14A ...) are not in G6's definition. They
     are measured beside it as context, never added in.
2. **The book**, through the canonical harness: `build_targets()`, the live
   policy `band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)` (spec v7, read
   through spec.py), `total_returns` (H15), `evaluate()` (shift(2): decided at
   t, filled at t+1's close, earning t+2).
3. **The cost.** `M[t, i]` = name i is under a pending event as known at the
   DECISION on t: first filing date <= t <= end date. (A filing dated t was
   public by 17:30 ET on t, EDGAR Filer Manual [S], and the book decides in the
   evening; `fetch_edgar_events` docstring.) The event shorts are
   `S = H.where((H < 0) & M, 0)`; `evaluate(S, R)["pnl"]` is exactly the P&L
   those positions earned under the house convention, because evaluate is
   linear in H. Their cost is minus that. It is set against the cost grid per
   year: the live book's turnover per year times 5 / 15 / 30bp, over the same
   days. Both readings of "the cost grid per year" are printed (book turnover
   x c, and the bare 5/15/30bp of book), so the verdict does not hang on one.
4. **A second measurement**, independent of the panel: the same event-short
   positions priced on CRSP daily total returns (`crsp_events.daily`, pre-2023
   by construction). The two must agree in sign and roughly in size; if they
   disagree, both are printed and neither is picked.

ALIGNMENT, ONCE MORE
--------------------
M uses only filings dated on or before the decision date; an episode's END
date is known only afterwards, but a filter that stays on until the event
resolves needs no knowledge of when that will be -- it switches off when the
result is filed. The mask is therefore causal for a filter that holds until
the final filing. `assert_causal` checks that no window starts before its
first filing.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:  # run as a script, not -m
    sys.path.insert(0, str(REPO))

OUT = REPO / "results" / "events"
G6_DIR = OUT / "g6"                               # the gate's outputs: the note sits in OUT, its data here
SUMMARY_OUT = G6_DIR / "g6_summary.json"
EVENTS_OUT = G6_DIR / "g6_events_13_names.csv"    # EDGAR facts only (public): tracked
COST_GRID_BP = (5, 15, 30)
ERAS = [("2013-14", "2013-01-01", "2014-12-31"), ("2015-19", "2015-01-01", "2019-12-31"),
        ("2020-22", "2020-01-01", "2022-12-31")]
G6_KINDS = ("nav_tender", "merger_target", "merger_acquirer", "liquidation")

# ---------------------------------------------------------------- parsers

_TITLE_RE = re.compile(r"\(\s*TITLE\s+OF\s+CLASS\s+OF\s+SECURITIES\s*\)")


def _plain(text: str) -> str:
    t = html.unescape(re.sub(r"<[^>]{0,400}>", " ", text))
    return re.sub(r"\s+", " ", t).upper()


def classify_tender(text: str) -> str:
    """'preferred', 'common' or 'unknown', from the cover page of a Schedule TO.

    The cover page names the class sought just above "(Title of Class of
    Securities)". Only that line decides: an offer document for common shares
    may mention the fund's preferreds and vice versa, so a whole-document word
    count would be wrong in both directions. Every occurrence of the cover
    line is read (an amendment can repeat it); disagreement is 'unknown'.
    """
    t = _plain(text)
    found = set()
    for m in _TITLE_RE.finditer(t):
        head = t[max(0, m.start() - 250):m.start()]
        # the class is the text after the previous cover-page label, which ends in ")"
        head = head.split(")")[-1]
        if "PREFERRED" in head:
            found.add("preferred")
        elif "COMMON" in head or "SHARES OF BENEFICIAL INTEREST" in head:
            found.add("common")
    if len(found) == 1:
        return found.pop()
    return "unknown"


_PROXY_PATTERNS = {
    "liquidation": r"PLAN OF (?:COMPLETE )?LIQUIDATION|LIQUIDAT(?:E|ION) (?:OF )?THE FUND|TO LIQUIDATE",
    "open_end": r"CONVER(?:T|SION)[^.]{0,80}OPEN-END|OPEN-END (?:FUND|INVESTMENT COMPANY)[^.]{0,40}CONVER",
    "termination": r"TERMINATION OF THE FUND|TERMINATE THE FUND|DISSOLUTION OF THE FUND",
    "tender_offer": r"TENDER OFFER",
    "merger": r"REORGANIZATION|MERGER",
}


def scan_proxy(text: str) -> dict[str, str]:
    """Each pattern found in a proxy or 8-K, with 160 characters around the
    first hit, for a reader to judge. A hit is a lead, not a classification:
    proxies describe shareholder PROPOSALS that the board opposes, and
    activist letters mention liquidation as a threat."""
    t = _plain(text)
    out = {}
    for k, p in _PROXY_PATTERNS.items():
        m = re.search(p, t)
        if m:
            out[k] = t[max(0, m.start() - 80):m.end() + 80]
    return out


# ------------------------------------------------------------------ masks

def event_mask(index: pd.DatetimeIndex, columns, windows: pd.DataFrame) -> pd.DataFrame:
    """Boolean frame: True where ticker is inside [start, end] (inclusive) of
    any window. `windows` has ticker, start, end."""
    M = pd.DataFrame(False, index=index, columns=list(columns))
    for w in windows.itertuples():
        if w.ticker not in M.columns:
            raise KeyError(f"window for {w.ticker}, which is not in the book")
        if pd.Timestamp(w.end) < pd.Timestamp(w.start):
            raise ValueError(f"{w.ticker}: window ends {w.end} before it starts {w.start}")
        M.loc[(index >= pd.Timestamp(w.start)) & (index <= pd.Timestamp(w.end)), w.ticker] = True
    return M


def assert_causal(windows: pd.DataFrame) -> None:
    """No window may open before the filing that made the event public."""
    bad = windows[pd.to_datetime(windows["start"]) < pd.to_datetime(windows["first_filing"])]
    if len(bad):
        raise AssertionError(f"windows open before their first filing: {bad[['ticker', 'start']].values.tolist()}")


def event_short_pnl(H: pd.DataFrame, R: pd.DataFrame, M: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    """(daily P&L, positions) of the shorts the book held under a pending event,
    through the canonical `evaluate` (shift(2) applied inside it)."""
    from scripts.cef.band_frontier import evaluate
    if not (H.index.equals(M.index) and list(H.columns) == list(M.columns)):
        raise ValueError("H and the event mask must share index and columns")
    S = H.where((H < 0) & M, 0.0)
    return evaluate(S, R)["pnl"], S


# ------------------------------------------------------------------ build

def thirteen(client) -> pd.DataFrame:
    """The spec's universe with each fund's CIK from the SEC ticker file."""
    from scripts.cef.spec import UNIVERSE
    from scripts.data import fetch_edgar_events as fe
    tk = fe.sec_tickers(client)
    m = tk[tk["ticker"].isin(UNIVERSE)]
    missing = sorted(set(UNIVERSE) - set(m["ticker"]))
    if missing:
        raise LookupError(f"no SEC CIK for spec names {missing}")
    if m["ticker"].duplicated().any():
        raise LookupError(f"ticker maps to two CIKs: {m[m['ticker'].duplicated(keep=False)].values.tolist()}")
    return m[["ticker", "cik", "name"]].reset_index(drop=True)


def edgar_events(client, funds: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Every tender, merger and contest episode, and every proxy/8-K lead, of the 13."""
    from scripts.data import fetch_edgar_events as fe
    from scripts.data.edgar_client import filing_txt_url
    eps, leads = [], []
    for f in funds.itertuples():
        s = fe.submissions(client, int(f.cik), max_age_s=7 * fe.DAY)
        s = s.rename(columns={"filingDate": "date_filed", "accessionNumber": "accession"})
        s["kind"] = s["form"].map(fe.FORM_KIND)
        e = fe.episodes(s.dropna(subset=["kind"]))
        e["ticker"] = f.ticker
        for r in e.itertuples():
            rec = r._asdict()
            if r.kind == "tender":
                g = s[(s["kind"] == "tender") & (s["date_filed"] >= pd.Timestamp(r.first_date))
                      & (s["date_filed"] <= pd.Timestamp(r.last_date))]
                # Every filing of the episode is read; an amendment that does
                # not repeat the cover line reads "unknown" and is ignored if a
                # cover line elsewhere in the episode names the class.
                classes = {classify_tender(client.get_text(filing_txt_url(int(f.cik), acc)))
                           for acc in g["accession"]}
                named = classes - {"unknown"}
                rec["security"] = named.pop() if len(named) == 1 else "unknown"
            if r.kind == "merger":
                g = s[(s["kind"] == "merger") & (s["date_filed"] >= pd.Timestamp(r.first_date))
                      & (s["date_filed"] <= pd.Timestamp(r.last_date))]
                rec["role"] = "acquirer" if g["form"].isin(["N-14 8C", "N-14 8C/A", "N-14"]).any() else "target"
            eps.append(rec)
        for x in s[s["form"].isin(["PRE 14A", "PRER14A", "8-K"])].itertuples():
            hits = scan_proxy(client.get_text(filing_txt_url(int(f.cik), x.accession)))
            if any(k in hits for k in ("liquidation", "open_end", "termination", "tender_offer")):
                leads.append({"ticker": f.ticker, "form": x.form, "date_filed": x.date_filed.date(),
                              "accession": x.accession, **{f"hit_{k}": v for k, v in hits.items()}})
    return pd.DataFrame(eps), pd.DataFrame(leads)


def crsp_completions(tickers) -> pd.DataFrame:
    """CRSP delistings INTO each of our funds (merger 2xx or exchange 3xx codes):
    the completion dates of the mergers in which a spec name was the acquirer.
    Names and delistings only (no returns)."""
    from scripts.events import crsp_events as ce
    nm, dl = ce.names(), ce.delistings()
    up = ce.universe_permnos(nm)
    rows = []
    for tk in tickers:
        for p in up[tk]:
            d = dl[(dl["nwperm"] == p) & (dl["dlstcd"] // 100).isin([2, 3])]
            for r in d.itertuples():
                rows.append({"ticker": tk, "acq_permno": p, "target_permno": int(r.permno),
                             "completion": r.dlstdt, "dlstcd": int(r.dlstcd)})
    return pd.DataFrame(rows, columns=["ticker", "acq_permno", "target_permno", "completion", "dlstcd"])


def target_first_filings(client, comps: pd.DataFrame) -> pd.DataFrame:
    """For each merger INTO a spec name, the earliest 425 / merger proxy indexed
    under a TARGET in the 730 days before completion -- a deal can be announced
    under the targets before the acquirer files anything (its N-14 8C comes
    later). Targets are CRSP funds; their CIKs come from the same name matcher
    as the merger-pair dates (`edgar_merger_dates.match_cik`), and an unmatched
    target is reported, not guessed."""
    from scripts.events import crsp_events as ce
    from scripts.events import edgar_merger_dates as emd
    if comps.empty:
        return pd.DataFrame(columns=["ticker", "completion", "target_permno", "status", "first_date", "first_form"])
    names, idx = emd.name_table(client, date.today())
    nm = ce.names()
    last = ce.last_name(nm).set_index("permno")
    rows = []
    for c in comps.itertuples():
        C = pd.Timestamp(c.completion)
        rec = {"ticker": c.ticker, "completion": C.date(), "target_permno": c.target_permno}
        m = emd.match_cik(last.loc[c.target_permno, "comnam"], names, C - pd.Timedelta(days=emd.WINDOW_DAYS), C)
        rec["status"] = m["status"]
        if m["status"] == "matched":
            g = idx[(idx["cik"] == m["cik"]) & idx["form"].isin(emd.ANNOUNCE_FORMS_TARGET)
                    & (idx["date_filed"] >= C - pd.Timedelta(days=emd.WINDOW_DAYS)) & (idx["date_filed"] < C)]
            if len(g):
                g = g.sort_values("date_filed").iloc[0]
                rec.update({"target_cik": m["cik"], "first_date": g["date_filed"].date(), "first_form": g["form"]})
        rows.append(rec)
    return pd.DataFrame(rows)


def windows_from(eps: pd.DataFrame, comps: pd.DataFrame, tfirst: pd.DataFrame) -> pd.DataFrame:
    """The G6 windows (and the contest context windows) from the episodes.

    A merger episode in which the spec name is the acquirer starts at the
    earlier of its own first filing and the earliest target filing for the
    same completion (`target_first_filings`)."""
    rows = []
    for e in eps.itertuples():
        start, end = pd.Timestamp(e.first_date), pd.Timestamp(e.last_date)
        first_filing = start
        if e.kind == "tender":
            kind = "nav_tender" if e.security == "common" else f"tender_{e.security}"
        elif e.kind == "merger":
            kind = f"merger_{e.role}"
            c = comps[(comps["ticker"] == e.ticker) & (comps["completion"] >= start)
                      & (comps["completion"] <= start + pd.Timedelta(days=730))]
            if len(c):
                end = max(end, pd.Timestamp(c["completion"].max()))
                end_basis = f"CRSP completion ({len(c)} delistings, codes {sorted(set(c['dlstcd']))})"
                t = tfirst[(tfirst["ticker"] == e.ticker)
                           & pd.to_datetime(tfirst["completion"]).isin(pd.to_datetime(c["completion"]))]
                t = t.dropna(subset=["first_date"]) if "first_date" in t else t.iloc[0:0]
                if len(t) and pd.Timestamp(t["first_date"].min()) < start:
                    start = first_filing = pd.Timestamp(t["first_date"].min())
            else:
                end_basis = "last filing (no CRSP delisting into this fund)"
        else:
            kind = e.kind
        rows.append({"ticker": e.ticker, "kind": kind, "start": start.date(), "end": end.date(),
                     "first_filing": first_filing.date(), "first_form": e.first_form, "last_filing": e.last_date,
                     "end_basis": end_basis if e.kind == "merger" else "last filing",
                     "n_filings": e.n_filings, "forms": e.forms})
    return pd.DataFrame(rows)


def measure(windows: pd.DataFrame) -> dict:
    """Run the harness and price the event shorts. Fit period only."""
    from scripts.cef.band_frontier import (band_gross_capped, build_targets, evaluate, fit_only,
                                           total_returns)
    from scripts.cef.spec import BAND_WIDTH, MAX_GROSS_STRESS, summary
    T, R_px = build_targets()
    T, R_px = fit_only(T, R_px)
    R = total_returns(R_px)
    assert R.index.max() < pd.Timestamp("2023-01-01")
    H = band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)
    live = H.abs().sum(axis=1) > 0
    first = live.idxmax()
    book = evaluate(H, R)
    act = slice(first, None)
    years = len(H.loc[act]) / 252.0
    turn_yr = float(book["turn_series"].loc[act].sum() / years)
    ann_ret = float(book["pnl"].loc[act].sum() / years)
    res = {"spec": summary(), "panel_first_trade": str(first.date()), "fit_last_date": str(H.index[-1].date()),
           "active_days": int(len(H.loc[act])), "active_years": round(years, 2),
           "book": {"ann_ret_pct": round(ann_ret * 100, 3), "turn_per_yr": round(turn_yr, 2),
                    "gross_sr_active": round(float(book["pnl"].loc[act].mean() / book["pnl"].loc[act].std() * np.sqrt(252)), 3),
                    "cost_grid_per_yr_bp": {f"{c}bp": round(turn_yr * c, 1) for c in COST_GRID_BP}}}
    out = {}
    for label, kinds in (("G6: nav_tender + merger + liquidation", G6_KINDS),
                         ("nav_tender", ("nav_tender",)), ("merger_acquirer", ("merger_acquirer",)),
                         ("merger_target", ("merger_target",)), ("liquidation", ("liquidation",)),
                         ("context: tender_preferred", ("tender_preferred",)),
                         ("context: contest", ("contest",))):
        w = windows[windows["kind"].isin(kinds)]
        M = event_mask(H.index, H.columns, w) if len(w) else pd.DataFrame(False, index=H.index, columns=H.columns)
        pnl, S = event_short_pnl(H, R, M)
        Lpos = H.where((H > 0) & M, 0.0)
        lp = evaluate(Lpos, R)["pnl"]
        short_days = int(((H < 0) & M).sum().sum())
        cost_bp_yr = -float(pnl.loc[act].sum()) / years * 1e4
        rec = {"windows": int(len(w)), "name_days_in_window_while_book_live": int(M.loc[act].sum().sum()),
               "short_name_days": short_days,
               "short_name_days_share_of_all_shorts": round(short_days / max(int((H < 0).sum().sum()), 1), 4),
               "names_shorted": sorted(c for c in H.columns if ((H[c] < 0) & M[c]).any()),
               "mean_short_weight": round(float(S[S < 0].stack().mean()), 4) if short_days else None,
               "short_pnl_total_bp": round(float(pnl.sum()) * 1e4, 2),
               "cost_bp_per_yr": round(cost_bp_yr, 2),
               "vs_grid_turnover_x_c": {f"{c}bp": round(cost_bp_yr - turn_yr * c, 2) for c in COST_GRID_BP},
               "long_pnl_total_bp_context": round(float(lp.sum()) * 1e4, 2),
               "by_era_short_pnl_bp": {lab: round(float(pnl.loc[a:b].sum()) * 1e4, 2) for lab, a, b in ERAS},
               "by_name_short_pnl_bp": {c: round(float((S[c].shift(2).fillna(0) * R[c]).sum()) * 1e4, 2)
                                        for c in H.columns if (S[c] != 0).any()},
               "by_window_short_days_and_pnl_bp": {
                   f"{x.ticker} {x.start}..{x.end}": [
                       int(((H[x.ticker] < 0) & (H.index >= pd.Timestamp(x.start)) & (H.index <= pd.Timestamp(x.end))).sum()),
                       round(float((S[x.ticker].where((S.index >= pd.Timestamp(x.start)) & (S.index <= pd.Timestamp(x.end)), 0.0)
                                    .shift(2).fillna(0) * R[x.ticker]).sum()) * 1e4, 2)]
                   for x in w.itertuples() if pd.Timestamp(x.end) >= first}}
        # the filter's turnover: zeroing these shorts and re-entering after the window
        if short_days:
            Hf = H.where(~((H < 0) & M), 0.0)
            rf = evaluate(Hf, R)
            dturn = float((rf["turn_series"].loc[act].sum() - book["turn_series"].loc[act].sum()) / years)
            rec["filter_dturn_per_yr"] = round(dturn, 3)
            rec["filter_net_gain_bp_per_yr"] = {f"{c}bp": round(cost_bp_yr - dturn * c, 2) for c in COST_GRID_BP}
        out[label] = rec
    res["measures"] = out
    res["_H"], res["_R"] = H, R
    return res


def crsp_check(H: pd.DataFrame, windows: pd.DataFrame) -> dict:
    """The G6 event-short P&L again, on CRSP daily total returns instead of the
    panel (an independent price source). Pre-2023 by construction."""
    from scripts.cef.band_frontier import evaluate
    from scripts.events import crsp_events as ce
    nm = ce.names()
    up = ce.universe_permnos(nm)
    w = windows[windows["kind"].isin(G6_KINDS)]
    M = event_mask(H.index, H.columns, w)
    S = H.where((H < 0) & M, 0.0)
    names = [c for c in H.columns if (S[c] != 0).any()]
    if not names:
        return {"names": [], "note": "no event shorts to check"}
    perms = {c: up[c] for c in names}
    d = ce.daily([p for ps in perms.values() for p in ps])
    R = pd.DataFrame(index=H.index, columns=names, dtype=float)
    for c, ps in perms.items():
        g = d[d["permno"].isin(ps)].set_index("date")["ret"]
        if g.index.duplicated().any():
            raise ValueError(f"{c}: two CRSP permnos price the same date")
        R[c] = g.reindex(H.index)
    # Only the days the positions earn on must be priced; a gap there raises.
    earn = S[names].shift(2).fillna(0.0) != 0
    gaps = int((earn & R.isna()).sum().sum())
    if gaps:
        raise ValueError(f"CRSP has no return on {gaps} event-short earning days")
    pnl = evaluate(S[names], R.fillna(0.0))["pnl"]   # fillna only off the earning days (checked above)
    return {"names": names, "short_pnl_total_bp_crsp": round(float(pnl.sum()) * 1e4, 2)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args(argv)
    from scripts.data.edgar_client import EdgarClient
    client = EdgarClient(offline=a.offline)
    funds = thirteen(client)
    eps, leads = edgar_events(client, funds)
    comps = crsp_completions(funds["ticker"])
    tfirst = target_first_filings(client, comps)
    windows = windows_from(eps, comps, tfirst)
    assert_causal(windows)
    res = measure(windows)
    H = res.pop("_H")
    res.pop("_R")
    res["crsp_check"] = crsp_check(H, windows)
    res["windows"] = windows.astype(str).to_dict(orient="records")
    res["proxy_8k_leads"] = leads.astype(str).to_dict(orient="records")
    # The leads are READ, not counted: a hit is a word, not a proposal. The
    # reading of 2026-10-12 is recorded in results/events/EDGAR_EVENTS_2026-10-12.md
    # §3; this field says how many leads there were for that reading to cover.
    res["proxy_8k_leads_n"] = int(len(leads))
    # CRSP permnos are licensed identifiers: not written to the tracked summary.
    res["merger_target_first_filings"] = (tfirst.drop(columns=["target_permno"], errors="ignore")
                                          .astype(str).to_dict(orient="records"))
    res["funds"] = funds.astype(str).to_dict(orient="records")
    res["edgar_fetch"] = {"requests": client.n_requests, "cache_hits": client.n_cache_hits}
    G6_DIR.mkdir(parents=True, exist_ok=True)
    windows.to_csv(EVENTS_OUT, index=False)
    SUMMARY_OUT.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps({k: res[k] for k in ("spec", "panel_first_trade", "book", "measures", "crsp_check")},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
