"""Explore: year-end tax-loss selling and the January rebound in closed-end funds.

    QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_cefs.py
    QUANTT_ENV_FILE=<env> python3 results/ideas/cef_tax_loss_january/stage.py
    python3 results/ideas/cef_tax_loss_january/explore.py

THE IDEA. Closed-end funds are held almost wholly by taxable individuals. A fund that is down
on the year is sold in November and December to realise the loss, and no institution steps in
to take the other side, so the price is pushed below where it would otherwise be and comes
back in January when the selling stops.

FIXED BEFORE ANY RETURN WAS READ (2026-11-16; only counts and quote coverage had been looked at)
  universe   every closed-end fund on CRSP, dead ones included
             (~/quantt_research/crsp_cef_daily.parquet, to 2025-12-31).
  seasons    formation years 2000..2024: 25 seasons, each one observation. (2025 is formed
             and described but has no January in the panel.)
  formation  F = the close of the TENTH session of December.
  signal     total return (CRSP, distributions included) from the close of the year's FIRST
             session to F. A fund needs a price on that first session and at F, and at most
             five sessions without a return in between.
  eligible   at F: price >= $2 and mean dollar volume over the 21 sessions ending F >= $500,000.
             (Also shown at $100,000.)
  book       long the worst FIFTH of eligible funds by the signal, equal weights, against
             every eligible fund equally weighted (the CEF market; losers are in it).
             Separately against the best fifth, which would need borrow.
  timing     decided at F, bought at the close of F+1, so the first return earned is F+2's
             (the desk's shift(2)). Sold at the close of the TENTH session of January
             (primary), and separately at January's last close.
  headline   ONE NUMBER A SEASON: the buy-and-hold return of the worst fifth from the F+1
             close to the exit close, less the same for all eligible funds. 25 numbers; their
             mean, t, and the count above zero. The calendar-time book on the canonical
             harness is shown beside it; it holds constant daily weights, which rebalances
             daily at closing prices and flatters thin funds (results/ideas/2026-11-16_net_cash.md),
             so the buy-and-hold figure is the one to believe when they differ.
  controls   (1) PLACEBO, two months later: the same sort on the return from the first
                 session of March to the tenth session of February, held from the next close
                 to the tenth session of March (and to March's last). If losers simply
                 reverse (or simply keep losing) at any time of year, this scores the same.
             (2) ORDINARY SMALL CAPS: the same rule on US common stocks ranked 1,501-4,000 by
                 market value (~/quantt_research/crsp_top4500_daily.parquet), same floors,
                 against their own equal-weighted average. If this scores as well, it is the
                 general January effect and not a CEF effect.
             (3) SHORT-TERM REVERSAL: the worst fifth by the last 63 sessions' return to F,
                 same holding period. If this scores as well, it is reversal, not tax.
  variant    (pre-named) formation at the last session of November, same exits.
  quotes     rescored from the mid of CRSP's closing bid and ask at entry and exit, and with
             entry one session later (a skip day), because a December close in a sold-off
             thin fund tends to sit on the bid and a January close on the ask.
  expected   worst fifth beats the CEF market from mid-December to mid-January by more than
             a round-trip spread, in most years; the placebo near zero; small caps smaller.

LOOKAHEAD. Everything that selects a fund is dated F or earlier (asserted in `season`), and
the first return counted is F+2's. A fund with no row after entry has stopped trading: CRSP
puts the delisting return on its last row, and later sessions earn zero (cash).
Returns are CRSP total returns, so a distribution's ex-date price drop is not read as a loss.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from scripts.research import explore, harness  # noqa: E402

assert pd.get_option("compute.use_numexpr") is False      # scripts/research/explore.py says why
HERE = Path(__file__).resolve().parent
RES = Path.home() / "quantt_research"
PANEL = RES / "crsp_cef_daily.parquet"
QUOTES = RES / "cef_tax_loss_january" / "cef_quotes.parquet"
PCEF = RES / "cef_tax_loss_january" / "pcef_yf.parquet"
SMALL = RES / "crsp_top4500_daily.parquet"
YF = RES / "yf_daily.parquet"
MIN_PRICE, FLOOR, FLOOR_LOW = 2.0, 500_000.0, 100_000.0
YEARS = range(2000, 2025)
ERAS = (("2002-08", 2002, 2008), ("2009-15", 2009, 2015), ("2016-19", 2016, 2019),
        ("2020-22", 2020, 2022), ("2023-24", 2023, 2024))


def nth(idx: pd.DatetimeIndex, year: int, month: int, n: int) -> pd.Timestamp:
    """The n-th session of a month (n = -1: the last). Raises if the month is short of it."""
    s = idx[(idx.year == year) & (idx.month == month)]
    if len(s) < abs(n) or len(s) < 15:
        raise ValueError(f"{year}-{month:02d} has {len(s)} sessions in the panel")
    return s[n - 1] if n > 0 else s[n]


def season(ret, prc, dv, *, sig_first, F, exits: dict, floor: float, extra=None) -> pd.DataFrame:
    """One formation: per fund, the signal, the fifths, and buy-and-hold returns to each exit.

    ALIGNMENT: `ytd`, `r3`, `adv` and the price filter read rows dated <= F only (asserted).
    `bh_*` compounds returns from F+2 (bought at the F+1 close) to the exit close.
    """
    idx = ret.index
    iF = idx.get_loc(F)
    E = idx[iF + 1] if iF + 1 < len(idx) else None
    win = ret.loc[idx[idx.get_loc(sig_first) + 1]:F]
    assert win.index.max() == F and sig_first < F
    ok = prc.loc[sig_first].notna() & prc.loc[F].notna() & (win.isna().sum() <= 5)
    ytd = ((1 + win.fillna(0.0)).prod() - 1).where(ok)
    w3 = ret.iloc[iF - 62:iF + 1]
    assert w3.index.max() == F
    r3 = ((1 + w3.fillna(0.0)).prod() - 1).where(w3.notna().sum() >= 58)
    a = dv.iloc[iF - 20:iF + 1]
    assert a.index.max() == F
    adv = a.mean().where(a.notna().sum() >= 10)
    el = ok & (prc.loc[F] >= MIN_PRICE) & (adv >= floor)
    if extra is not None:
        el &= extra.reindex(el.index).fillna(False)
    d = pd.DataFrame({"ytd": ytd, "r3": r3, "adv": adv, "prc": prc.loc[F]})[el]
    n = len(d)
    d["q"] = np.ceil(d["ytd"].rank(method="first") / n * 5).astype(int)
    d["dec"] = np.ceil(d["ytd"].rank(method="first") / n * 10).astype(int)
    d["q3"] = np.ceil(d["r3"].rank(method="first") / d["r3"].notna().sum() * 5)
    d["rk"] = (d["ytd"].rank() - 0.5) / n
    d["rk3"] = (d["r3"].rank() - 0.5) / d["r3"].notna().sum()
    for name, X in exits.items():
        assert X > E
        iX = idx.get_loc(X)
        d[f"bh_{name}"] = ((1 + ret.iloc[iF + 2:iX + 1][d.index].fillna(0.0)).prod() - 1)
        d[f"skip_{name}"] = ((1 + ret.iloc[iF + 3:iX + 1][d.index].fillna(0.0)).prod() - 1)
        d[f"gone_{name}"] = prc.loc[X, d.index].isna()
    d.attrs.update(F=F, E=E, exits=exits)
    return d


def ann(x: pd.Series) -> dict:
    """The statistics of a set of one-a-season figures."""
    x = x.dropna()
    n, sd = len(x), x.std()
    return {"n": int(n), "mean": float(x.mean()), "median": float(x.median()), "sd": float(sd),
            "t": float(x.mean() / sd * np.sqrt(n)), "n_pos": int((x > 0).sum()),
            "min": float(x.min()), "max": float(x.max()),
            "first_half_mean": float(x.iloc[:n // 2].mean()), "second_half_mean": float(x.iloc[n // 2:].mean()),
            "eras": {k: {"mean": float(x.loc[a:b].mean()), "n_pos": int((x.loc[a:b] > 0).sum()), "n": int(len(x.loc[a:b]))}
                     for k, a, b in ERAS}}


def spread_rows(seasons: dict, col: str, pick=lambda d: d["q"] == 1) -> dict:
    """Per season: picked funds less all eligible, picked less the best fifth, picked raw."""
    out = {}
    for y, d in seasons.items():
        p = pick(d)
        out[y] = {"lm": d.loc[p, col].mean() - d[col].mean(), "lw": d.loc[p, col].mean() - d.loc[d["q"] == 5, col].mean(),
                  "raw": d.loc[p, col].mean(), "mkt": d[col].mean(), "n": int(len(d)), "n_pick": int(p.sum())}
    return pd.DataFrame(out).T


def clustered(e: pd.Series, g: pd.Series) -> dict:
    """Mean of per-fund excess returns with a t clustered by season (one event month a season)."""
    m, N = e.mean(), len(e)
    s = (e - m).groupby(g).sum()
    G = len(s)
    se = np.sqrt((s ** 2).sum() * G / (G - 1)) / N
    return {"n": int(N), "mean": float(m), "median": float(e.median()), "share_pos": float((e > 0).mean()),
            "t_clustered": float(m / se), "p05": float(e.quantile(.05)), "p25": float(e.quantile(.25)),
            "p75": float(e.quantile(.75)), "p95": float(e.quantile(.95))}


def cal_book(seasons: dict, exit_name: str, ret: pd.DataFrame, pick=lambda d: d["q"] == 1) -> pd.DataFrame:
    """Weights DECIDED each session: +1 across picked funds, -1 across all eligible, from F to
    two sessions before the exit, so the harness's shift(2) earns F+2 .. exit."""
    idx = ret.index
    H = pd.DataFrame(0.0, index=idx, columns=ret.columns)
    for d in seasons.values():
        iF, iX = idx.get_loc(d.attrs["F"]), idx.get_loc(d.attrs["exits"][exit_name])
        rows = idx[iF:iX - harness.EXEC_LAG + 1]
        L = d.index[pick(d)]
        H.loc[rows, d.index] -= 1.0 / len(d)
        H.loc[rows, L] += 1.0 / len(L)
    return H


def small_cap_seasons() -> dict:
    """Control 2: the same rule on common stocks ranked 1,501-4,000, a season at a time."""
    con = duckdb.connect()
    cal = pd.DatetimeIndex(con.execute(f"select distinct date from '{SMALL}' order by 1").df()["date"])
    out = {}
    for y in YEARS:
        df = con.execute(f"""select permno, date, ret, prc, dollar_volume, cap_rank from '{SMALL}'
                             where date >= '{y}-01-01' and date <= '{y + 1}-01-31'""").df()
        df["date"] = pd.to_datetime(df["date"])
        ret, prc, dv = (df.pivot(index="date", columns="permno", values=c) for c in ("ret", "prc", "dollar_volume"))
        F = nth(cal, y, 12, 10)
        rk = df[df["date"] == F].set_index("permno")["cap_rank"]
        out[y] = season(ret, prc, dv, sig_first=nth(cal, y, 1, 1), F=F, floor=FLOOR, extra=rk.between(1501, 4000),
                        exits={"j10": nth(cal, y + 1, 1, 10), "jend": nth(cal, y + 1, 1, -1)})
    return out


def main() -> int:
    df = pd.read_parquet(PANEL)
    df["date"] = pd.to_datetime(df["date"])
    last = df["date"].max().date()
    ret, prc, dv, div = (df.pivot(index="date", columns="permno", values=c) for c in ("ret", "prc", "dollar_volume", "div"))
    idx = ret.index
    q = pd.read_parquet(QUOTES)
    q["date"] = pd.to_datetime(q["date"])
    bid, ask, vol = (q.pivot(index="date", columns="permno", values=c).reindex(index=idx, columns=ret.columns) for c in ("bid", "ask", "vol"))
    good = (bid > 0) & (ask >= bid)
    mid = ((bid + ask) / 2).where(good)
    spr = ((ask - bid) / mid).where(good)

    def build(kind: str, floor: float) -> dict:
        out = {}
        for y in YEARS:
            if kind == "dec":
                kw = dict(sig_first=nth(idx, y, 1, 1), F=nth(idx, y, 12, 10),
                          exits={"j10": nth(idx, y + 1, 1, 10), "jend": nth(idx, y + 1, 1, -1)})
            elif kind == "nov":
                kw = dict(sig_first=nth(idx, y, 1, 1), F=nth(idx, y, 11, -1),
                          exits={"j10": nth(idx, y + 1, 1, 10), "jend": nth(idx, y + 1, 1, -1)})
            elif kind == "placebo":
                kw = dict(sig_first=nth(idx, y, 3, 1), F=nth(idx, y + 1, 2, 10),
                          exits={"j10": nth(idx, y + 1, 3, 10), "jend": nth(idx, y + 1, 3, -1)})
            out[y] = season(ret, prc, dv, floor=floor, **kw)
        return out

    main_s, low_s, nov_s, plc_s = build("dec", FLOOR), build("dec", FLOOR_LOW), build("nov", FLOOR), build("placebo", FLOOR)
    sc_s = small_cap_seasons()
    r3pick = lambda d: d["q3"] == 1

    # ---- the one-a-season figures -------------------------------------------------------
    T = {"main_j10": spread_rows(main_s, "bh_j10"), "main_jend": spread_rows(main_s, "bh_jend"),
         "low_j10": spread_rows(low_s, "bh_j10"), "nov_j10": spread_rows(nov_s, "bh_j10"),
         "placebo_10": spread_rows(plc_s, "bh_j10"), "placebo_end": spread_rows(plc_s, "bh_jend"),
         "smallcap_j10": spread_rows(sc_s, "bh_j10"), "smallcap_jend": spread_rows(sc_s, "bh_jend"),
         "r3_j10": spread_rows(main_s, "bh_j10", r3pick), "skip_j10": spread_rows(main_s, "skip_j10")}
    res = {"panel_last_date": str(last), "small_cap_panel_last_date": str(duckdb.connect().execute(f"select max(date) from '{SMALL}'").fetchone()[0]),
           "seasons": len(main_s), "annual": {}}
    for k, t in T.items():
        res["annual"][k] = {"loser_minus_market": ann(t["lm"]), "loser_minus_winner": ann(t["lw"]), "loser_raw": ann(t["raw"]),
                            "market_raw": ann(t["mkt"]), "funds_eligible_mean": float(t["n"].mean()), "funds_held_mean": float(t["n_pick"].mean())}
    res["annual"]["cef_minus_smallcap_j10"] = ann(T["main_j10"]["lm"] - T["smallcap_j10"]["lm"])
    res["annual"]["main_minus_placebo_j10"] = ann(T["main_j10"]["lm"] - T["placebo_10"]["lm"])
    res["annual"]["main_minus_r3_j10"] = ann(T["main_j10"]["lm"] - T["r3_j10"]["lm"])

    # ---- tradable hedges: PCEF (from 2010) and IWM ---------------------------------------
    pc = pd.read_parquet(PCEF).set_index("date")["ret_total"]
    yf = pd.read_parquet(YF)
    iwm = yf[yf["ticker"] == "IWM"].set_index("date")["ret_total"]
    hedge = {}
    for name, s in (("pcef", pc), ("iwm", iwm)):
        s = s.copy(); s.index = pd.to_datetime(s.index)
        rows = {}
        for y, d in main_s.items():
            iF, iX = idx.get_loc(d.attrs["F"]), idx.get_loc(d.attrs["exits"]["j10"])
            w = s.reindex(idx[iF + 2:iX + 1])
            if w.isna().any():
                continue                                   # the ETF was not listed for the whole window
            rows[y] = d.loc[d["q"] == 1, "bh_j10"].mean() - ((1 + w).prod() - 1)
        hedge[name] = pd.Series(rows)
        res["annual"][f"loser_minus_{name}_j10"] = ann(hedge[name])

    # ---- per-season table ------------------------------------------------------------------
    tab = pd.DataFrame({"eligible": T["main_j10"]["n"], "held": T["main_j10"]["n_pick"],
                        "ytd_cut": pd.Series({y: d.loc[d["q"] == 1, "ytd"].max() for y, d in main_s.items()}),
                        "loser": T["main_j10"]["raw"], "market": T["main_j10"]["mkt"], "L-M j10": T["main_j10"]["lm"],
                        "L-M jend": T["main_jend"]["lm"], "L-W j10": T["main_j10"]["lw"], "placebo": T["placebo_10"]["lm"],
                        "small caps": T["smallcap_j10"]["lm"], "3m losers": T["r3_j10"]["lm"], "L-PCEF": hedge["pcef"]})
    res["per_season"] = {int(y): {k: (None if pd.isna(v) else float(v)) for k, v in r.items()} for y, r in tab.iterrows()}

    # ---- per fund: distribution within the worst fifth, the ladder, mid quotes ------------
    rows = []
    for y, d in main_s.items():
        E, X = d.attrs["E"], d.attrs["exits"]["j10"]
        d = d.copy()
        d["year"] = y
        d["ex"] = d["bh_j10"] - d["bh_j10"].mean()
        d["ex_end"] = d["bh_jend"] - d["bh_jend"].mean()
        aE, aX = (mid.loc[E, d.index] / prc.loc[E, d.index]), (mid.loc[X, d.index] / prc.loc[X, d.index])
        d["bh_mid"] = (1 + d["bh_j10"]) * aX / aE - 1          # NaN unless a two-sided quote at both ends
        d["spr_E"], d["spr_X"] = spr.loc[E, d.index], spr.loc[X, d.index]
        d["close_vs_mid_E"] = 1 / aE - 1                         # close above (+) or below (-) the mid at entry
        d["close_vs_mid_X"] = 1 / aX - 1
        d["novol_E"], d["novol_X"] = ~(vol.loc[E, d.index] > 0), ~(vol.loc[X, d.index] > 0)
        iE, iX = idx.get_loc(E), idx.get_loc(X)
        d["n_ex"] = (div.iloc[iE + 1:iX + 1][d.index] > 0).sum()
        rows.append(d)
    A = pd.concat(rows)
    L = A[A["q"] == 1]
    res["per_fund_losers_j10"] = clustered(L["ex"], L["year"])
    res["per_fund_losers_jend"] = clustered(L["ex_end"], L["year"])
    res["ladder_fifths_mean_excess_j10"] = {int(k): float(v) for k, v in A.groupby(["year", "q"])["ex"].mean().groupby("q").mean().items()}
    res["ladder_tenths_mean_excess_j10"] = {int(k): float(v) for k, v in A.groupby(["year", "dec"])["ex"].mean().groupby("dec").mean().items()}
    both = A["bh_mid"].notna()
    by = lambda col, m: pd.Series({y: g.loc[g["q"] == 1, col].mean() - g[col].mean() for y, g in A[m].groupby("year")})
    res["mid_quotes"] = {"share_of_eligible_fund_seasons_with_quotes_both_ends": float(both.mean()),
                         "share_of_losers_with_quotes_both_ends": float(both[A["q"] == 1].mean()),
                         "close_same_sample": ann(by("bh_j10", both)), "mid": ann(by("bh_mid", both)),
                         "losers_close_vs_mid_at_entry_bp": float(L["close_vs_mid_E"].mean() * 1e4),
                         "all_close_vs_mid_at_entry_bp": float(A["close_vs_mid_E"].mean() * 1e4),
                         "losers_close_vs_mid_at_exit_bp": float(L["close_vs_mid_X"].mean() * 1e4),
                         "all_close_vs_mid_at_exit_bp": float(A["close_vs_mid_X"].mean() * 1e4)}
    res["liquidity"] = {"losers_median_adv": float(L["adv"].median()), "all_median_adv": float(A["adv"].median()),
                        "losers_median_price": float(L["prc"].median()), "all_median_price": float(A["prc"].median()),
                        "losers_median_spread_entry_bp": float(L["spr_E"].median() * 1e4), "all_median_spread_entry_bp": float(A["spr_E"].median() * 1e4),
                        "losers_mean_spread_entry_bp": float(L["spr_E"].mean() * 1e4),
                        "losers_median_spread_exit_bp": float(L["spr_X"].median() * 1e4),
                        "losers_median_spread_entry_bp_2016_on": float(L.loc[L["year"] >= 2016, "spr_E"].median() * 1e4),
                        "losers_median_adv_2016_on": float(L.loc[L["year"] >= 2016, "adv"].median()),
                        "losers_share_no_volume_entry": float(L["novol_E"].mean()), "losers_share_no_volume_exit": float(L["novol_X"].mean()),
                        "losers_share_gone_by_exit": float(L["gone_j10"].mean()),
                        "ex_dates_in_hold_losers_mean": float(L["n_ex"].mean()), "ex_dates_in_hold_all_mean": float(A["n_ex"].mean())}
    # not pre-specified: which sort carries it? a cross-section a season of the hold return on both ranks (0..1)
    fm = {}
    for y, g in A.dropna(subset=["rk3"]).groupby("year"):
        Xm = np.column_stack([np.ones(len(g)), g["rk"], g["rk3"]])
        fm[y] = np.linalg.lstsq(Xm, g["bh_j10"].to_numpy(), rcond=None)[0][1:]
    fm = pd.DataFrame(fm, index=["ytd_rank", "r3_rank"]).T
    res["not_pre_specified_both_ranks"] = {c: ann(fm[c]) for c in fm}

    # ---- calendar-time books on the canonical harness --------------------------------------
    R = ret.fillna(0.0)                                   # no row = stopped trading (stage script); see LOOKAHEAD
    span = slice("2000-12-01", "2025-03-31")
    ev = {k: harness.evaluate(cal_book(s, x, ret, p), R) for k, (s, x, p) in
          {"main": (main_s, "j10", lambda d: d["q"] == 1), "placebo": (plc_s, "j10", lambda d: d["q"] == 1),
           "r3": (main_s, "j10", r3pick), "jend": (main_s, "jend", lambda d: d["q"] == 1)}.items()}
    pnl = ev["main"]["pnl"].loc[span]
    controls = {"placebo, Feb to Mar": ev["placebo"]["pnl"].loc[span], "worst fifth on 3 months": ev["r3"]["pnl"].loc[span]}
    book = explore.summarise(pnl, controls=controls, extra={"turnover_per_year": float(ev["main"]["turn"]),
                             "held_to_january_end": explore.stats(ev["jend"]["pnl"].loc[span])})
    res["calendar_book_per_1_long_1_short"] = book

    # ---- formation 2025: described, not scored (no January 2026 in the panel) ----------------
    d25 = season(ret, prc, dv, sig_first=nth(idx, 2025, 1, 1), F=nth(idx, 2025, 12, 10), exits={}, floor=FLOOR)
    l25 = d25[d25["q"] == 1]
    res["formation_2025"] = {"F": str(d25.attrs["F"].date()), "eligible": int(len(d25)), "worst_fifth": int(len(l25)),
                             "ytd_cut": float(l25["ytd"].max()), "ytd_median_of_fifth": float(l25["ytd"].median()),
                             "ytd_median_all": float(d25["ytd"].median()), "median_adv_of_fifth": float(l25["adv"].median()),
                             "share_of_fifth_below_zero_on_the_year": float((l25["ytd"] < 0).mean())}
    res["share_of_worst_fifth_below_zero_on_the_year"] = {int(y): float((d.loc[d["q"] == 1, "ytd"] < 0).mean()) for y, d in main_s.items()}

    explore.write(HERE, res, pnl, title=f"CEFs: worst fifth on the year less all, 10th Dec session to 10th Jan session; shift(2), gross; to {last}",
                  controls=controls)
    (HERE / "results.json").write_text(json.dumps(res, indent=1))

    # ---- print ---------------------------------------------------------------------------------
    pd.set_option("display.width", 250)
    print("panel to", last, "| seasons", len(main_s))
    print((tab * 100).round(2).assign(eligible=tab["eligible"], held=tab["held"]).to_string())
    print("\none figure a season (worst fifth less all eligible unless said), %:")
    for k, v in res["annual"].items():
        a = v.get("loser_minus_market", v)
        e = " ".join(f"{n}:{x['mean'] * 100:+.2f}({x['n_pos']}/{x['n']})" for n, x in a["eras"].items())
        print(f"  {k:26s} n {a['n']:2d} mean {a['mean'] * 100:+.2f} med {a['median'] * 100:+.2f} t {a['t']:+.2f} pos {a['n_pos']:2d} "
              f"min {a['min'] * 100:+.1f} max {a['max'] * 100:+.1f} halves {a['first_half_mean'] * 100:+.2f}/{a['second_half_mean'] * 100:+.2f} | {e}")
        if "loser_minus_winner" in v:
            w, r_, m = v["loser_minus_winner"], v["loser_raw"], v["market_raw"]
            print(f"  {'':26s} L-W mean {w['mean'] * 100:+.2f} t {w['t']:+.2f} pos {w['n_pos']} | loser raw {r_['mean'] * 100:+.2f} t {r_['t']:+.2f} pos {r_['n_pos']}"
                  f" | market raw {m['mean'] * 100:+.2f} | eligible {v['funds_eligible_mean']:.0f} held {v['funds_held_mean']:.0f}")
    for k in ("per_fund_losers_j10", "per_fund_losers_jend", "ladder_fifths_mean_excess_j10", "ladder_tenths_mean_excess_j10",
              "mid_quotes", "liquidity", "not_pre_specified_both_ranks", "formation_2025"):
        print(k, json.dumps(res[k], default=float)[:1500])
    print(explore.table(book))
    print("turnover/yr", round(book["turnover_per_year"], 2), "| held to January's end:", book["held_to_january_end"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
