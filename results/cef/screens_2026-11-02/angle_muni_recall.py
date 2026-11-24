"""Angle C: record-date borrow recall in muni CEFs (catalogue CORP row E3), tested on the IBKR
fee history instead of waiting for three months of Alpaca flags. Zero trials. No return is read.

MECHANISM. A short seller pays the lender a payment in lieu of each distribution. For a muni
CEF that payment is ordinary income to the lender, never the exempt-interest dividend the
holder bought the fund for (docs/REFERENCES.md, 'Payment in lieu' rows [V]/[S]). A taxable
lender of muni-CEF shares therefore has a monthly reason to recall before each record date and
re-lend after it. Recalls shrink the lendable pool -- which a fixed share count cannot grow --
so the borrow fee should rise into the record date and fall after the ex-date. Who loses: the
short, i.e. our book's muni shorts (MHD, MQY on Alpaca) in real money; paper charges no borrow.

NEGATIVE CONTROL (H12, named before the run). Taxable credit CEFs (hy, loan, multi, emd): their
distributions are ordinary (non-qualified) income either way, so a payment in lieu costs the
lender nothing in tax and there is no recall motive. The same event-time profile must be flat
there. A second control is a placebo event 10 sessions before each ex-date (mid-cycle for a
monthly payer): the muni profile must be flat around it too, or the shape is a calendar effect.

DATA. data/cef/cef_borrow_history.parquet: IBKR TWS FEE_RATE daily, 2021-09-13 -> 2026-09-09,
44 credit CEFs (REFERENCES row 'IBKR FEE_RATE daily history': [S] levels before 2026-09, [V]
the 2026-09-04 scale). Ex-dates: data/cef/cef_distributions.parquet. Groups: cef_universe.csv.
Fees are a cost, not a return; the headline window is the fit (ex-dates <= 2022-12-30). The
2023+ rows are reported separately as cost data, split at the T+1 settlement change
(2024-05-28; under T+2 the record date is ex + 1 session, under T+1 it is the ex-date).
ALIGNMENT: event time k counts the fee panel's own sessions for that name; the baseline is the
mean fee over k in [-20, -11], strictly before the window. Nothing after k = +10 is read.

Run from the repo root:  python3 -B results/cef/screens_2026-11-02/angle_muni_recall.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import angle_common as c                                         # noqa: E402

K = range(-10, 11)
BASE = range(-20, -10)
T1 = pd.Timestamp("2024-05-28")


def event_panel(fee: pd.DataFrame, ex: pd.DataFrame, shift: int = 0, log: bool = False) -> pd.DataFrame:
    """One row per (ticker, ex-date): fee[k] - mean(fee[BASE]) for k in K, in pct-pts/yr.
    `shift` moves the event date by that many fee sessions (the placebo uses -10)."""
    out = []
    for tk, g in ex.groupby("ticker"):
        if tk not in fee.columns:
            continue
        f = fee[tk].dropna()
        idx = f.index
        for d in g["ex_date"]:
            pos = idx.searchsorted(d)                 # first fee session on/after the ex-date
            if pos >= len(idx) or (idx[pos] - d).days > 4:
                continue
            pos += shift
            lo, hi = pos + min(BASE), pos + max(K)
            if lo < 0 or hi >= len(idx):
                continue
            if log:
                # robust version: log fee ratio to the baseline median (fees are heavily skewed;
                # a fee <= 0 cannot be logged and the event is skipped, counted below)
                seg = f.iloc[pos + min(BASE):pos + max(K) + 1]
                if (seg <= 0).any():
                    continue
                base = float(np.median(np.log(f.iloc[[pos + b for b in BASE]])))
                row = {k: float(np.log(f.iloc[pos + k])) - base for k in K}
            else:
                base = f.iloc[[pos + b for b in BASE]].mean()
                row = {k: f.iloc[pos + k] - base for k in K}
            row.update(ticker=tk, ex_date=d, base=base)
            out.append(row)
    return pd.DataFrame(out)


def profile(ev: pd.DataFrame, label: str):
    """Mean abnormal fee by k, t clustered by ex-date (same-day ex-dates within a family)."""
    rows = []
    for k in K:
        s = ev.groupby("ex_date")[k].mean()                # one obs per calendar ex-date
        rows.append(dict(k=k, mean=float(ev[k].mean()), median=float(ev[k].median()),
                         t_cluster=float(s.mean() / (s.std(ddof=1) / np.sqrt(len(s)))) if len(s) > 2 else np.nan))
    p = pd.DataFrame(rows).set_index("k")
    p.columns = pd.MultiIndex.from_product([[label], p.columns])
    return p


def window_stat(ev: pd.DataFrame, ks):
    v = ev[list(ks)].mean(axis=1)
    s = v.groupby(ev["ex_date"]).mean()
    return dict(mean=float(v.mean()), median=float(v.median()), t_cluster=float(s.mean() / (s.std(ddof=1) / np.sqrt(len(s)))),
                n_events=int(len(v)), n_dates=int(len(s)), base_median=float(ev["base"].median()))


def main():
    b = pd.read_parquet(c.REPO / "data" / "cef" / "cef_borrow_history.parquet")
    b["date"] = pd.to_datetime(b["date"])
    fee = b.pivot_table(index="date", columns="ticker", values="fee_rate_pct").sort_index()
    ex = pd.read_parquet(c.REPO / "data" / "cef" / "cef_distributions.parquet")[["ticker", "ex_date", "amount"]]
    ex["ex_date"] = pd.to_datetime(ex["ex_date"])
    u = pd.read_csv(c.REPO / "data" / "cef" / "cef_universe.csv")[["ticker", "grp"]]
    grp = dict(zip(u.ticker, u.grp))
    ex = ex[ex.ticker.isin(fee.columns)]
    ex = ex[(ex.ex_date >= fee.index.min() + pd.Timedelta(days=40))]
    out = dict(fee_panel=[str(fee.index.min().date()), str(fee.index.max().date())],
               dist_panel_last=str(ex.ex_date.max().date()), names=int(fee.shape[1]))

    windows = {"fit 2021-09..2022-12 (headline)": (None, c.FIT_END),
               "2023-01..2024-05-27 (T+2; cost data)": (pd.Timestamp("2023-01-01"), T1 - pd.Timedelta(days=1)),
               "2024-05-28.. (T+1; cost data)": (T1, None)}
    res = {}
    for wl, (a, z) in windows.items():
        e = ex.copy()
        if a is not None:
            e = e[e.ex_date >= a]
        if z is not None:
            e = e[e.ex_date <= z]
        evs = {}
        for side in ("muni", "taxable"):
            es = e[e.ticker.map(grp).eq("muni") == (side == "muni")]
            evs[side] = event_panel(fee, es)
            evs[side + "_placebo"] = event_panel(fee, es, shift=-10)
            evs[side + "_LOG"] = event_panel(fee, es, log=True)
            evs[side + "_LOG_placebo"] = event_panel(fee, es, shift=-10, log=True)
        if wl.startswith("fit"):
            for v in evs.values():
                c.assert_fit(v, "fee events")
        pre = range(-3, 1)                 # around the record date (ex+1 under T+2; ex under T+1)
        post = range(3, 8)
        r = {}
        for side, ev in evs.items():
            if len(ev) < 10:
                r[side] = dict(n_events=int(len(ev)))
                continue
            r[side] = dict(pre_record=window_stat(ev, pre), post_ex=window_stat(ev, post))
        # muni minus taxable, by matched calendar month (a crude calendar control)
        res[wl] = r
        print(f"\n== {wl}")
        for side, v in r.items():
            print(f"  {side:16s} {v}")
        if wl.startswith("fit"):
            prof = pd.concat([profile(evs["muni"], "muni"), profile(evs["taxable"], "taxable"),
                              profile(evs["muni_placebo"], "muni placebo (ex-10)")], axis=1)
            print("\n  fit profile, abnormal fee in pct-pts/yr by session k from the ex-date:")
            print(prof.round(3).to_string())
            out["fit_profile"] = {f"{a}|{b}": v for (a, b), v in prof.to_dict().items()}
    out["windows"] = res

    # what it would cost the real-money book: the fit book's mean muni short weight (unit book)
    T, R, R_tr, H, p = c.live_book()
    mun = [t for t in H.columns if grp.get(t) == "muni"]
    sh = (-H[mun].clip(upper=0)).sum(axis=1)
    m = (H.index >= "2020-01-01") & (H.abs().sum(axis=1) > 0)
    out["fit_book_muni_short_weight_2020_22"] = float(sh[m].mean())
    print(f"\nfit book (unit) mean muni short weight 2020-22: {sh[m].mean():.3f} of capital; names {mun}")
    (HERE / "angle_muni_recall_output.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
