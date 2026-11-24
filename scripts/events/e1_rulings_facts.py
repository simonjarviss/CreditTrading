"""The facts behind E1's rulings form (results/events/E1_RULINGS_FORM_2026-10-20.md). Zero trials.

    python3 scripts/events/e1_rulings_facts.py      # offline; prints, writes nothing tracked

1. THE 19 STAGE-0 FLAGS. For each flagged fit deal (`results/events/e1/e1_stage0_flags.csv`):
   whether the target has a CRSP return on its last session and the acquirer on the payment date,
   and the date of the acquirer permno's FIRST CRSP row. An acquirer whose first row is the
   payment date is a fund the merger created: there was no share to short at the A+1 fill.
   Reads the presence of returns and dates only; no return value is used.
2. READING R10'S ALTERNATIVE. Of DG-E1-3's candidate episodes (`e1_failed_census.csv`), how many
   have the episode's OWN CIK matched (`e1_merger_pair.crsp_cik_map`) to a CRSP CEF permno (share
   code 14/44) on an exchange (exchcd 1-3) on the first filing date, and how many of the rest carry
   an EDGAR name `merger_pairs.classify` labels a BDC (share code 11, outside the CEF map). Names
   and CIKs only.
Run 2026-10-20: 18 acquirers begin on the payment date, 1 (BLJ's) has no CRSP name; 857 CEF
permnos map to a unique CIK; of 273 candidates 75 are listed CEFs (22 run past CRSP's end) and
21 of the rest are BDC-named.
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
pd.set_option("compute.use_numexpr", False)
from scripts.events import e1_merger_pair as e1  # noqa: E402
from scripts.events import edgar_merger_dates as emd  # noqa: E402
from scripts.events import merger_pairs as mp  # noqa: E402


def flag_legs(nm, dl) -> pd.DataFrame:
    x = e1.deal_table(nm, dl)
    xf = e1.attach_dates(x[x["part"] == e1.FIT_SET], e1.load_fit_dates(x))
    etf = {int(nm[(nm["ticker"] == tk) & (nm["shrcd"] == 73) & (nm["nameendt"] >= e1.FIT_START)]["permno"].iloc[0])
           for tk in e1.ETF_TICKERS}
    dsf = e1.fit_daily(set(xf["permno"].astype(int)) | set(xf["nwperm"].astype(int)) | etf)
    px, cal = e1.price_series(dsf), e1.market_calendar(dsf, e1.FIT_START, e1.FIT_END)
    flags = pd.read_csv(e1.STAGE0_FLAGS, dtype=str)
    rows = []
    for _, e in xf.iterrows():
        w = e1.deal_window(e, px, cal)
        if not (w and not w["why"]) or not ((flags["ticker"] == e["ticker"]) & (flags["date"] == str(w["d_in"].date()))).any():
            continue
        T, A = px[int(e["permno"])], px[int(e["nwperm"])]
        rows.append({"target": e["ticker"], "acquirer": e["a_ticker"], "d_in": str(w["d_in"].date()),
                     "dlpdt": str(e["dlpdt"].date()),
                     "target_ret_last_session": bool(e["dlstdt"] in T.index and pd.notna(T.at[e["dlstdt"], "ret"])),
                     "acquirer_ret_payment_day": bool(e["dlpdt"] in A.index and pd.notna(A.at[e["dlpdt"], "ret"])),
                     "acquirer_first_row": str(A.index.min().date()),
                     "acquirer_begins_on_payment_date": bool(A.index.min() == e["dlpdt"])})
    return pd.DataFrame(rows)


def _names():
    """EDGAR's name table for these zero-trial facts, read from the cache AS CACHED. The open
    quarter's index is otherwise re-fetched daily (`quarter_is_closed`, max_age one day), which only
    a credentialed run can do. Here, unlike Stage 0, a stale copy is used and its fetch time printed:
    it can lack only filings after that time, and no census window reaches 2026. Stage 0 keeps the
    strict rule (`e1_merger_pair.refresh_edgar_index`)."""
    from scripts.data.edgar_client import EdgarClient, cache_path

    class AsCached(EdgarClient):
        def get(self, url, max_age_s=None):
            p = cache_path(url, self.cache)
            if max_age_s is not None and p.exists():
                print(f"  (as cached: {url.rsplit('/edgar/', 1)[-1]} fetched {date.fromtimestamp(p.stat().st_mtime)})")
                return p.read_bytes()
            return super().get(url, max_age_s)
    names, _ = emd.name_table(AsCached(offline=True, cache=e1.EDGAR_UNION), date(2026, 10, 19))
    return names


def own_listed(nm, names=None) -> dict:
    """episode id -> True if the episode's own CIK maps to a CRSP CEF listed on its first filing date,
    or its EDGAR name is BDC-like (the R10 count's two tests, per episode)."""
    cmap = e1.crsp_cik_map(nm, _names() if names is None else names)
    inv: dict[int, set] = {}
    for p, c in cmap.items():
        inv.setdefault(c, set()).add(p)
    cen = pd.read_csv(e1.CENSUS)
    cen["first_date"] = pd.to_datetime(cen["first_date"])
    out = {}
    for r in cen.itertuples():
        ok = any(len(x := nm[(nm["permno"] == p) & (nm["namedt"] <= r.first_date) & (nm["nameendt"] >= r.first_date)])
                 and x["exchcd"].isin([1, 2, 3]).any() for p in inv.get(int(r.episode_cik), ()))
        out[f"{int(r.episode_cik)}_{r.episode_accession}"] = bool(ok or mp.classify(str(r.company_last).upper()) == "bdc")
    return out


def r10(nm) -> dict:
    cmap = e1.crsp_cik_map(nm, _names())
    inv: dict[int, set] = {}
    for p, c in cmap.items():
        inv.setdefault(c, set()).add(p)
    cen = pd.read_csv(e1.CENSUS)
    cen["first_date"] = pd.to_datetime(cen["first_date"])

    def listed(r):
        for p in inv.get(int(r.episode_cik), ()):
            x = nm[(nm["permno"] == p) & (nm["namedt"] <= r.first_date) & (nm["nameendt"] >= r.first_date)]
            if len(x) and x["exchcd"].isin([1, 2, 3]).any():
                return True
        return False

    cen["listed_cef"] = [listed(r) for r in cen.itertuples()]
    bdc = cen["company_last"].astype(str).str.upper().map(mp.classify) == "bdc"
    return {"cef_permnos_mapped": len(cmap), "candidates": len(cen), "listed_cef": int(cen["listed_cef"].sum()),
            "listed_cef_past_crsp": int(cen.loc[cen["listed_cef"], "window_past_crsp"].sum()),
            "rest_bdc_named": int((~cen["listed_cef"] & bdc).sum())}


def main() -> int:
    nm, dl = e1.crsp_tables()
    f = flag_legs(nm, dl)
    print(f.to_string(index=False))
    print(f"flags: {len(f)}; acquirer begins on the payment date: {int(f['acquirer_begins_on_payment_date'].sum())}; "
          f"acquirer with no CRSP name: {int(f['acquirer'].isna().sum())}")
    print(r10(nm))
    return 0


if __name__ == "__main__":
    sys.exit(main())
