"""Does a recent share offering spoil a small-stock earnings-drift long?

    python3 results/ideas/pead_small/issuance_filter.py

WHY: the niche hunt of 2026-11-15 (results/ideas/2026-11-15_niche_hunt.md, "dilution-armed
flag") proposed that a company which has just sold shares is a worse drift long: it has
shown it will issue into strength, and the buyers of the offering are sellers on good news.
The skeptic's objection stands in the header on purpose: this is a second look at a sample
the desk has already read (results/ideas/2026-11-15_pead_small.md), so an improvement is
one more try on the same 2000-2025 data.

FIXED BEFORE ANY FILTERED RETURN WAS READ (2026-11-15):
  BASE     the long tenth of results/ideas/pead_small/explore.py, surprise sort, unchanged.
  FLAG     the stock priced a follow-on offering (SDC, the staged file of
           scripts/research/stage_sdc_follow_ons.py) on a date strictly before the decision
           session t and no more than 90 calendar days before it. Strictly before: an
           offering priced on t after the close is not known at t's close.
  CLEAN    the long tenth with flagged names removed after the sort, the rest reweighted
           equally. FLAGGED: the removed names alone, equally weighted.
  VARIANT  PRIMARY: the flag only when the company itself sold shares (primary shares > 0),
           since a holder's secondary sale is not dilution.
  EXPECTED FLAGGED below BASE; CLEAN at or above BASE. Each against IWM, shift(2), gross.
A session on which a book holds no name earns zero on both legs. Prints the table and
writes issuance_filter.json beside this file (aggregates only).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False
HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ps", HERE / "explore.py")
ps = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ps)
pw = ps.pw
WINDOW_DAYS = 90
ERAS = {"2002-08": ("2002", "2008"), "2009-15": ("2009", "2015"), "2016-19": ("2016", "2019"), "2020-22": ("2020", "2022"), "2023-25": ("2023", "2025")}


def flag_frame(fo: pd.DataFrame, sessions: pd.DatetimeIndex, columns) -> pd.DataFrame:
    """True on sessions t with an issue date in [t - 90 days, t), per permno.
    ALIGNMENT: the first flagged session is the first one strictly after the issue date."""
    f = np.zeros((len(sessions), len(columns)), dtype=bool)
    col = {p: i for i, p in enumerate(columns)}
    for p, d in zip(fo["permno"].to_numpy(), pd.to_datetime(fo["issue_date"]).to_numpy()):
        j = col.get(p)
        if j is None:
            continue
        a = sessions.searchsorted(d, side="right")
        b = sessions.searchsorted(d + np.timedelta64(WINDOW_DAYS, "D"), side="right")
        f[a:b, j] = True
    out = pd.DataFrame(f, index=sessions, columns=columns)
    return out


def main() -> int:
    df = pd.read_parquet(ps.PANEL, columns=["permno", "date", "ret", "prc", "cap_rank", "dollar_volume"])
    df["date"] = pd.to_datetime(df["date"])
    ret = df.pivot(index="date", columns="permno", values="ret")
    prc = df.pivot(index="date", columns="permno", values="prc").astype("float32")
    rank = df.pivot(index="date", columns="permno", values="cap_rank").astype("float32")
    adv = df.pivot(index="date", columns="permno", values="dollar_volume").rolling(21, min_periods=10).mean()
    del df
    ok = (rank > ps.RANK_LO) & (rank <= ps.RANK_HI) & (prc >= ps.MIN_PRICE) & (adv >= ps.MIN_ADV)
    R = ret.fillna(0.0)
    sessions = ret.index
    yf = pd.read_parquet(ps.RES / "yf_daily.parquet")
    iwm = yf[yf["ticker"] == "IWM"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"].reindex(sessions)
    ev = pd.read_parquet(pw.EVENTS)
    ev = ev[ev["permno"].isin(ret.columns)].copy()
    ev["t"] = pw.known_session(ev, sessions)
    e = ev.dropna(subset=["suescore", "t"]).sort_values(["t", "anndats"]).drop_duplicates(["t", "permno"], keep="last")
    S = e.pivot(index="t", columns="permno", values="suescore").reindex(index=sessions, columns=ret.columns)
    H = pw.book(S.ffill(limit=ps.HOLD - 1).where(ok))
    longs = H > 0
    fo = pd.read_parquet(ps.RES / "sdc_follow_ons.parquet")
    flags = {"any offering": flag_frame(fo, sessions, ret.columns),
             "primary shares sold": flag_frame(fo[fo["primary_shares"].fillna(0) > 0], sessions, ret.columns)}

    def leg(mask: pd.DataFrame) -> tuple:
        w = mask.astype(float)
        n = w.sum(axis=1)
        w = w.div(n.where(n > 0), axis=0).fillna(0.0)
        p = harness.evaluate(w, R)["pnl"]
        held = harness.held(w).sum(axis=1) > 0
        return (p - iwm.where(held, 0.0)).loc["2000-06-01":].dropna(), n

    def row(label, p, n, out):
        s = explore.stats(p)
        out[label] = {**{k: s[k] for k in ("sharpe", "t", "ann_ret", "ann_vol", "n_active_days")},
                      "names_per_day": float(n.loc[p.index].mean()),
                      "halves": [explore.stats(p.iloc[:len(p) // 2])["sharpe"], explore.stats(p.iloc[len(p) // 2:])["sharpe"]],
                      "by_era": {k: explore.stats(p.loc[a:b])["sharpe"] for k, (a, b) in ERAS.items()}}
        o = out[label]
        print(f"  {label:38s} SR {o['sharpe']:.2f} (t {o['t']:.2f}) ret {o['ann_ret']:.2%} vol {o['ann_vol']:.2%} names {o['names_per_day']:.1f} "
              f"| halves {o['halves'][0]:.2f}/{o['halves'][1]:.2f} | " + " ".join(f"{k}:{v:.2f}" if v is not None else f"{k}:n/a" for k, v in o["by_era"].items()))

    out = {"panel_last_date": str(sessions[-1].date()), "window_days": WINDOW_DAYS, "follow_ons_in_file": int(len(fo))}
    base, nb = leg(longs)
    row("BASE long tenth", base, nb, out)
    for name, fl in flags.items():
        share = float((longs & fl).sum().sum() / longs.sum().sum())
        print(f" flag: {name}; {share:.1%} of long name-days are flagged")
        out[f"share_flagged, {name}"] = share
        c, nc = leg(longs & ~fl)
        f, nf = leg(longs & fl)
        row(f"CLEAN ({name})", c, nc, out)
        row(f"FLAGGED ({name})", f, nf, out)
        d = (c - base.reindex(c.index)).dropna()
        out[f"CLEAN less BASE ({name})"] = {"ann_ret": float(d.mean() * 252), "t": float(d.mean() / d.std() * len(d) ** 0.5)}
        print(f"  CLEAN less BASE: {d.mean() * 252:.2%} a year (t {out[f'CLEAN less BASE ({name})']['t']:.2f})")
    (HERE / "issuance_filter.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
