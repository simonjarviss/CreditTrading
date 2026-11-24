"""Explore: buying the issuer after a convertible issue. The follow-on test's rule, unchanged.

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_sdc_convertibles.py
    python3 results/ideas/convert_issuance/explore.py

FIXED BEFORE ANY RETURN WAS READ (2026-11-15). Only counts had been looked at: 3,337 SDC
convertible issues since 2000 matched to a CRSP common share (about 130 a year), 1,403 of
them in a public market; 2,786 carry no launch date, so the launch cut of the follow-on test
is not available here.

  RULE      results/ideas/follow_ons/explore.py's REBOUND book, imported and not edited:
            D = SDC's issue date; decided at the close of D+1 (price >= $2, 21-session dollar
            volume >= $500,000); long 10% a name against IWM, pro rata above 50%; earns D+3
            through D+7. The same two controls (30 sessions earlier, 30 later).
  EXPECTED SIGN, written down first: positive. Buyers of a convertible who hedge sell the
            share short when the deal prices; that selling is temporary.
  WHAT IS NOT NEW. The desk measured this once (E2, results/events/REPRO_CORP_EVENTS_2026-10-11.md):
            +0.54% over days 2 to 5 on 755 TRACE-dated events of 2011-22, fading to +0.17% in
            2020-22. Those years have been looked at. SDC's 2000-2010 and 2023-2025 have not.
  DESCRIPTIVE ONLY: by era; 2011-22 against the years outside it; public against private
            and 144A markets; names trading $5M a day; the event-time profile, D-5 to D+15.

NOT MODELLED: nothing on the long side. The DRIFT short of the follow-on test is not run.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore  # noqa: E402

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("fo_explore", HERE.parent / "follow_ons" / "explore.py")
fo = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(fo)


def load():
    """The follow-on loader on the convertible files (same columns)."""
    ev = pd.read_parquet(fo.RES / "sdc_convertibles.parquet")
    px = pd.read_parquet(fo.RES / "crsp_convertible_daily.parquet")
    yf = pd.read_parquet(fo.RES / "yf_daily.parquet")
    for c in ("issue_date", "launch", "filed"):
        ev[c] = pd.to_datetime(ev[c])
    px["date"] = pd.to_datetime(px["date"])
    iwm = yf[yf["ticker"] == "IWM"].assign(date=lambda d: pd.to_datetime(d["date"])).set_index("date")["ret_total"].dropna()
    sessions = pd.DatetimeIndex(sorted(px["date"].unique()))
    sessions = sessions[(sessions >= iwm.index.min()) & (sessions <= iwm.index.max())]
    if iwm.reindex(sessions).isna().any():
        raise ValueError("IWM has no return on a CRSP session inside its own range")
    piv = lambda col: px.pivot(index="date", columns="permno", values=col).reindex(sessions)  # noqa: E731
    return ev, piv("ret"), piv("prc"), piv("dollar_volume"), iwm.reindex(sessions), sessions


def main() -> int:
    ev, ret, prc, dv, iwm, sessions = load()
    adv = dv.rolling(21, min_periods=10).mean()
    R = ret.copy(); R["IWM"] = iwm
    e = fo.place(ev, sessions, prc, adv)
    e["public"] = e["market"].str.contains("public", case=False, na=False)
    yr = sessions[e["d"].to_numpy()].year
    out = {"panel_first_date": str(sessions[0].date()), "panel_last_date": str(sessions[-1].date()),
           "counts": {"placed": int(len(e)), "eligible": int(e["ok"].sum()), "eligible_public": int((e["ok"] & e["public"]).sum())}}
    print(json.dumps(out["counts"], indent=1))
    pnl, meta = fo.run(e, "rebound", sessions, R)
    controls = {"same events, 30 sessions earlier": fo.run(e, "rebound", sessions, R, shift=-30)[0],
                "same events, 30 sessions later": fo.run(e, "rebound", sessions, R, shift=30)[0]}
    res = explore.summarise(pnl, controls=controls, extra=meta)
    res["by_era"] = {k: explore.stats(pnl.loc[a:b]) for k, (a, b) in fo.ERAS.items()}
    res["cuts"] = {}
    for k, sub in {"issued 2011-22 (seen by E2)": e[(yr >= 2011) & (yr <= 2022)], "issued outside 2011-22": e[(yr < 2011) | (yr > 2022)],
                   "public market": e[e["public"]], "private and 144A": e[~e["public"]],
                   "$5M a day": e[e["adv_dec"] >= 5e6], "$20M a day": e[e["adv_dec"] >= 2e7]}.items():
        p, m = fo.run(sub, "rebound", sessions, R)
        res["cuts"][k] = {**explore.stats(p), "events_traded": m["events_traded"]}
    out["rebound"] = res
    explore.write(HERE, res, pnl, controls=controls,
                  title=f"Convertible issues, long D+3..D+7: 10% a name vs IWM; shift(2), gross; to {out['panel_last_date']}")
    print(f"\n== rebound: events {meta['events_traded']:,} ({meta['events_per_year']:.0f}/yr) | invested {meta['share_of_days_invested']:.0%} | "
          f"names held {meta['mean_names_held']:.1f} | missing-return name-days {meta['held_name_days_with_no_return']} of {meta['held_name_days']}")
    print(explore.table(res))
    print("  by era:", " | ".join(f"{b}: SR {v['sharpe']:.2f} t {v['t']:.1f}" for b, v in res["by_era"].items()))
    print("  cuts:", " | ".join(f"{b}: SR {v['sharpe']:.2f} t {v['t']:.1f} n {v['events_traded']}" for b, v in res["cuts"].items()))
    out["profile"] = fo.profile(e[e["ok"]], ret, iwm, -5, 15)
    print("\nprofile (bp, t by month):", " ".join(f"{a}:{v['mean_bp']:+.0f}({v['t_by_month']:+.1f})" for a, v in out["profile"].items()))
    (HERE / "results_full.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
