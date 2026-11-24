"""Tests for the NAV-tender trial script (EVENTS trial 2). Synthetic data only: these test the code,
never a claim about the market. No network (the root conftest blocks it), no CRSP, no EDGAR cache.

The P&L tests build a tender with a known payoff by hand and check every number the matrices and
`band_frontier.evaluate` produce, the shift(2) alignment (nothing earned before day 0 + 2 or after
F + 1), and that the per-event ledger reconciles to the sleeve.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from scripts.events import nav_tender_trial as T


# ----------------------------------------------------------------- constants pinned to the prereg

def test_declared_constants():
    from scripts.cef.band_frontier import HOLDOUT_START
    assert T.HOLDOUT_START == HOLDOUT_START
    assert (T.N_BAR, T.CUTOFF_SESSIONS, T.RESIDUAL_LAG, T.EXCLUSION_MAX) == (6, 3, 5, 0.20)
    assert (T.T_BAR, T.ALPHA_T_BAR, T.BETA_MAX, T.STAGE3_BP, T.DSR_PASS) == (2.0, 3.0, 0.10, 15, 0.95)
    assert T.COSTS_BP == (5, 15, 30) and T.SEED == 20261019 and T.PLACEBO_DRAWS == 1000


# ----------------------------------------------------------------- the tender row and the matrices

def sessions(n=40, start="2015-03-02"):
    return pd.DatetimeIndex([d for d in pd.bdate_range(start, periods=n + 10) if T.is_session(d)][:n])


def one_event(S, pi=0.4, p_final=10.20, beta=0.5, d0=5, xp=15, F=22, u=1.0):
    return T.Ev(eid="E1", group="G1", day0=S[d0], F=S[F], x_p=S[xp], pi=pi, p_final=p_final, u=u, beta=beta, etf="ETF")


def test_tender_return_formula():
    # accepted 40% at 10.20 against a 9.50 close; residual earns +1%
    r = T.tender_return(0.4, 10.20, 9.50, 0.01)
    assert r == pytest.approx(0.4 * (10.20 / 9.50 - 1) + 0.6 * 0.01)
    with pytest.raises(T.TrialError):
        T.tender_return(1.2, 10.0, 9.0, 0.0)
    with pytest.raises(T.TrialError):
        T.tender_return(0.5, 10.0, float("nan"), 0.0)


def test_synthetic_tender_known_payoff():
    """Fund +0.1% a day, ETF +0.2% a day, close 9.50 before pricing, P_final 10.20, pi 0.4, beta 0.5.
    Expected per-unit P&L, by hand: the fund leg earns 0.1% on day0+2 .. X_p-1, the tender row on X_p,
    (1 - pi) * 0.1% on X_p+1 .. F+1; the hedge loses 0.5 * 0.2% on every P&L session."""
    S = sessions()
    e = one_event(S)
    fr = pd.Series(0.001, index=S)
    fc = pd.Series(9.50, index=S)
    er = pd.Series(0.002, index=S)
    M = T.build_matrices([e], {"E1": fr}, {"E1": fc}, {"ETF": er}, S)
    H, R, Q = M["H"], M["R"], M["Q"]
    # decisions: weight u on [day0, F); the hedge -beta*u on the same rows
    assert (H.loc[S[5]:S[21], "E1"] == 1.0).all() and H.loc[S[22]:, "E1"].eq(0).all() and H.loc[:S[4], "E1"].eq(0).all()
    assert (H.loc[S[5]:S[21], "ETF"] == -0.5).all()
    # the tender row and the residual
    assert R.loc[S[15], "E1"] == pytest.approx(0.4 * (10.20 / 9.50 - 1) + 0.6 * 0.001)
    assert np.allclose(R.loc[S[16]:S[23], "E1"], 0.6 * 0.001)
    # traded notional: 1 in, (1 - pi) out; the hedge 0.5 in and out
    assert Q.loc[S[5], "E1"] == 1.0 and Q.loc[S[22], "E1"] == pytest.approx(0.6)
    assert Q["ETF"].sum() == pytest.approx(1.0)
    pnl = T.sleeve_pnl(M)
    n_pre = 15 - 7                   # day0+2 = S[7] .. X_p-1 = S[14]
    n_post = 23 - 15                 # X_p+1 .. F+1 = S[23]
    n_all = 23 - 7 + 1
    expect = (n_pre * 0.001 + (0.4 * (10.20 / 9.50 - 1) + 0.6 * 0.001) + n_post * 0.6 * 0.001) - 0.5 * 0.002 * n_all
    assert pnl.sum() == pytest.approx(expect)
    led = M["ledger"]["E1"]
    assert led["first_pl"] == S[7] and led["last_pl"] == S[23] and led["sessions"] == n_all
    assert led["pnl_fund"] + led["pnl_hedge"] == pytest.approx(expect)


def test_shift2_alignment_no_lookahead():
    """A huge return on the entry session (day 0 + 1, before the close fill) or after F + 1 must never
    reach the P&L; the first P&L session is day 0 + 2 and the last F + 1 (H1/H7)."""
    S = sessions()
    e = one_event(S, pi=0.0, xp=15)
    e = T.Ev(**{**e.__dict__, "x_p": None})          # a terminated offer: no tender row
    fr = pd.Series(0.0, index=S)
    fr.loc[S[6]] = 5.0                                # day 0 + 1: bought at its close, not earned
    fr.loc[S[24]] = -5.0                              # F + 2: sold at the close of F + 1
    M = T.build_matrices([e], {"E1": fr}, {"E1": pd.Series(10.0, index=S)}, {"ETF": pd.Series(0.0, index=S)}, S)
    pnl = T.sleeve_pnl(M)
    assert pnl.abs().sum() == 0.0
    fr2 = fr.copy()
    fr2.loc[S[7]] = 0.01                              # day 0 + 2: the first P&L session
    fr2.loc[S[23]] = 0.02                             # F + 1: the last
    M2 = T.build_matrices([e], {"E1": fr2}, {"E1": pd.Series(10.0, index=S)}, {"ETF": pd.Series(0.0, index=S)}, S)
    assert T.sleeve_pnl(M2).sum() == pytest.approx(0.03)


def test_tender_row_must_be_inside_the_hold():
    S = sessions()
    e = one_event(S, xp=6)                            # pricing on day 0 + 1: no position yet
    with pytest.raises(AssertionError, match="pricing session"):
        T.build_matrices([e], {"E1": pd.Series(0.0, index=S)}, {"E1": pd.Series(10.0, index=S)},
                         {"ETF": pd.Series(0.0, index=S)}, S)


def test_nan_return_on_a_held_day_raises():
    S = sessions()
    e = one_event(S)
    fr = pd.Series(0.001, index=S)
    fr.loc[S[10]] = np.nan
    with pytest.raises(AssertionError, match="not finite on a held day"):
        T.build_matrices([e], {"E1": fr}, {"E1": pd.Series(9.5, index=S)}, {"ETF": pd.Series(0.0, index=S)}, S)


def test_hedges_net_per_etf_and_ledger_reconciles():
    S = sessions(60)
    a = T.Ev("A", "G1", S[5], S[25], S[15], 0.3, 11.0, 0.5, 0.8, "HYG")
    b = T.Ev("B", "G1", S[5], S[30], S[18], 0.5, 9.0, 0.5, 1.2, "HYG")
    c = T.Ev("C", "G2", S[20], S[45], S[33], 1.0, 20.0, 1.0, 0.4, "SPY")
    rng = np.random.default_rng(1)
    fr = {k: pd.Series(rng.normal(0, 0.01, len(S)), index=S) for k in "ABC"}
    fc = {k: pd.Series(10.0, index=S) for k in "ABC"}
    er = {k: pd.Series(rng.normal(0, 0.01, len(S)), index=S) for k in ("HYG", "SPY")}
    M = T.build_matrices([a, b, c], fr, fc, er, S)
    assert M["H"].loc[S[10], "HYG"] == pytest.approx(-(0.8 * 0.5 + 1.2 * 0.5))
    T.sleeve_pnl(M)                                   # raises if the ledger does not sum to evaluate()
    pe = T.per_event_table([a, b, c], M["ledger"], {"A": 0.3, "B": 0.5, "C": 1.0}, 15)
    row = pe.set_index("eid").loc["A"]
    assert row["net"] == pytest.approx(row["gross"] - 0.5 * 15e-4 * (1 + 0.7 + 1.6))


def test_twin_B_exits_before_pricing_and_never_tenders():
    S = sessions()
    e = one_event(S)
    pos = {d: i for i, d in enumerate(S)}
    fr = pd.Series(0.001, index=S)
    M = T.build_matrices([e], {"E1": fr}, {"E1": pd.Series(9.5, index=S)}, {"ETF": pd.Series(0.0, index=S)}, S,
                         exit_={"E1": S[pos[e.x_p] - 2]}, elect=False)
    assert M["ledger"]["E1"]["last_pl"] == S[14]                       # sold at the close of X_p - 1
    assert M["ledger"]["E1"]["pnl_fund"] == pytest.approx(0.001 * (14 - 7 + 1))
    assert M["Q"].loc[S[13], "E1"] == 1.0                              # the whole position sold


# ----------------------------------------------------------------- sizing and the cap

def test_capped_weights_scale_at_entry_and_never_cut():
    S = sessions(60)
    a = T.Ev("A", "G1", S[5], S[30], S[15], 0.3, 11.0, 1.0, 1.0, "HYG")
    b = T.Ev("B", "G2", S[10], S[35], S[20], 0.3, 11.0, 1.0, 1.0, "SPY")
    c = T.Ev("C", "G3", S[12], S[40], S[22], 0.3, 11.0, 1.0, 1.0, "SPY")
    w, s = T.capped_weights([a, b, c], k=0.6, sessions=S, cap=1.8)
    # A alone: gross 0.6 * 2 = 1.2 <= 1.8; B gets the room 0.6 -> scale 0.5; C finds no room
    assert s["A"] == 1.0 and s["B"] == pytest.approx(0.5, abs=1e-9) and s["C"] == 0.0
    assert w["A"] == pytest.approx(0.6) and w["B"] == pytest.approx(0.3, abs=1e-9) and w["C"] == 0.0


def test_sigma_active_ignores_idle_sessions():
    S = sessions(80)
    H = pd.DataFrame(0.0, index=S, columns=["E"])
    H.iloc[10:50] = 1.0
    pnl = pd.Series(0.0, index=S)
    pnl.iloc[12:52] = np.tile([0.01, -0.01], 20)
    assert T.sigma_active(pnl, H) == pytest.approx(pnl.iloc[12:52].std() * np.sqrt(252))


# ----------------------------------------------------------------- the hedge ratio: no lookahead

def _frame(rets, idx):
    from scripts.events import e1_etf_hedge_gate as g
    df = pd.DataFrame({"permno": 1, "date": idx, "ret": rets, "prc": 10.0, "vol": 1000.0})
    return g.series(df)[1]


def test_beta_uses_only_pre_window_data():
    idx = pd.DatetimeIndex([d for d in pd.bdate_range("2014-01-01", "2016-06-30") if T.is_session(d)])
    rng = np.random.default_rng(7)
    etf = rng.normal(0, 0.01, len(idx))
    fund = 0.7 * etf + rng.normal(0, 0.002, len(idx))
    day0 = idx[500]
    fund_after = fund.copy()
    fund_after[480:] = 5 * etf[480:]                  # anything from 42 sessions before day 0 on is ignored
    b1 = T.beta_for(_frame(fund, idx), _frame(etf, idx), day0)
    b2 = T.beta_for(_frame(fund_after, idx), _frame(etf, idx), day0)
    assert b1["status"] == "ok" and b1["beta"] == pytest.approx(b2["beta"], rel=1e-12)
    assert b1["beta"] == pytest.approx(0.7, abs=0.05)
    assert b1["est_end"] < day0
    short = T.beta_for(_frame(fund[:250], idx[:250]), _frame(etf, idx), idx[249])
    assert short["beta"] is None


# ----------------------------------------------------------------- calendar and day 0

def test_day0_session_rules():
    from scripts.events.event_store import ET
    # accepted 16:45 ET on a session: the 22:00 decision that day sees it
    t = datetime(2019, 3, 5, 16, 45, tzinfo=ET).astimezone(timezone.utc)
    assert T.day0_session(t) == pd.Timestamp("2019-03-05")
    # observed 22:30 ET: the next session's decision
    t = datetime(2019, 3, 5, 22, 30, tzinfo=ET).astimezone(timezone.utc)
    assert T.day0_session(t) == pd.Timestamp("2019-03-06")
    # observed on a Saturday: Monday
    t = datetime(2019, 3, 9, 10, 0, tzinfo=ET).astimezone(timezone.utc)
    assert T.day0_session(t) == pd.Timestamp("2019-03-11")


def test_observed_from_header_applies_the_max_rule():
    raw = "<SEC-HEADER>\n<ACCEPTANCE-DATETIME>20190305180600\nFILED AS OF DATE:\t\t20190306\n</SEC-HEADER>"
    obs, note = T.observed_from_raw(raw)
    assert note is None and T.day0_session(obs) == pd.Timestamp("2019-03-06")   # 06:00 ET on the 6th
    raw2 = "<SEC-HEADER>\n<ACCEPTANCE-DATETIME>20170519134157\nFILED AS OF DATE:\t\t20170518\n</SEC-HEADER>"
    obs2, note2 = T.observed_from_raw(raw2)
    assert note2 is not None and T.day0_session(obs2) == pd.Timestamp("2017-05-19")


def test_exit_session_and_periods():
    xp = pd.Timestamp("2019-04-16")
    assert T.exit_session(pd.Timestamp("2019-04-18"), xp) == T.add_sessions(xp, 5)
    assert T.exit_session(pd.Timestamp("2019-05-01"), xp) == pd.Timestamp("2019-05-01")
    assert T.exit_session(pd.Timestamp("2019-05-01"), None, terminated=True) == T.add_sessions(pd.Timestamp("2019-05-01"), 5)
    assert T.assign_period("2022-11-01", pd.Timestamp("2022-12-30")) == "fit"
    assert T.assign_period("2022-11-01", pd.Timestamp("2023-01-03")) == "gap"
    assert T.assign_period("2024-11-01", pd.Timestamp("2025-01-02")) == "after_crsp"


# ----------------------------------------------------------------- the readers

RESULT_1 = ("The Offer expired at 5:00 p.m. New York City time, on Tuesday, May 23, 2017. The Fund has accepted "
            "11,114,143 shares (subject to adjustment for fractional shares) for cash payment at a price equal to "
            "$12.15 per share. This purchase price is 98.5% of the Fund's net asset value per share of $12.33 as of the "
            "close of regular trading on the New York Stock Exchange on May 23, 2017. Par value $0.01 per share.")


def test_final_expiry_and_price_single_fund():
    e, sp = T.final_expiry(RESULT_1, pd.Timestamp("2017-04-20"), pd.Timestamp("2017-06-01"))
    assert e == pd.Timestamp("2017-05-23")
    pr = T.final_price(RESULT_1, "VLT", False, e)
    assert pr.p_final == 12.15 and pr.nav_date == pd.Timestamp("2017-05-23")
    # a "scheduled to expire" clause and a date outside the window are not the final expiry
    t = "The Offer, originally scheduled to expire on May 2, 2017, was extended. The Offer expired on May 9, 2017."
    assert T.final_expiry(t, pd.Timestamp("2017-04-01"), pd.Timestamp("2017-05-31"))[0] == pd.Timestamp("2017-05-09")
    assert T.final_expiry(t, pd.Timestamp("2017-05-10"), pd.Timestamp("2017-05-31"))[0] is None
    # "closed-end" is not "closed" (MCN 2018 read its Offer to Purchase date as the expiry)
    t2 = "The Fund is a diversified, closed-end company; its Offer to Purchase dated October 10, 2018 is amended."
    assert T.final_expiry(t2, pd.Timestamp("2018-10-10"), pd.Timestamp("2018-11-30"))[0] is None


def test_final_price_ignores_the_fee_block_unless_dated_at_expiry():
    fee = ("CALCULATION OF FILING FEE Transaction valuation $3,555,054.72 (a) based upon a price of $6.72 (98% of the "
           "net asset value per share of $6.86 on July 18, 2012). Amount Previously Paid: $407.41 ")
    body = "The Offer expired at 5:00 p.m. on August 22, 2012. The shares accepted for payment will receive cash at a repurchase offer price of $7.08, which is equal to 98% of the NAV."
    pr = T.final_price(fee + body, "EEA", False, pd.Timestamp("2012-08-22"))
    assert pr.p_final == 7.08
    fee2 = ("CALCULATION OF FILING FEE by $43.22, (98% of Net Asset Value per share) as of the close of ordinary "
            "trading on the New York Stock Exchange on May 23, 2017. Amount Previously Paid: $1 ")
    pr2 = T.final_price(fee2 + " The tender offer was oversubscribed.", "KF", False, pd.Timestamp("2017-05-23"))
    assert pr2.p_final == 43.22 and "fee block" in pr2.how
    assert T.final_price(fee2 + " Nothing else.", "KF", False, pd.Timestamp("2017-06-30")).p_final is None


def test_final_price_joint_releases_need_an_anchor():
    t = ("The shares accepted for payment will receive cash at a repurchase offer price of $15.12 for DHG and $8.64 "
         "for LBF, which is equal to 99% of each Fund's respective net asset value on November 22, 2010.")
    assert T.final_price(t, "LBF", True, None).p_final == 8.64
    t2 = ("The Funds accepted 3,373,469, 6,615,414 and 19,334,647 shares, for GLV, GLQ and GLO, respectively, for cash "
          "payment at a purchase price of $14.65, $14.42 and $12.01 per common share for GLV, GLQ and GLO, respectively.")
    assert T.final_price(t2, "GLQ", True, None).p_final == 14.42
    assert T.final_price(t2, None, True, None).p_final is None
    t3 = ("VLT: The Fund has accepted 11,114,143 shares for cash payment at a price equal to $12.15 per share. VVR: The "
          "Fund has accepted 1,623,686 shares for cash payment at a price equal to $15.13 per share.")
    assert T.final_price(t3, "VVR", True, None, accepted=1623686).p_final == 15.13
    # two different prices in a single-fund filing: a gap, never a pick
    t4 = "The Fund accepted 100,000 shares at a price of $10.00 per share. The purchase price is $10.50 per share."
    assert T.final_price(t4, "X", False, None).p_final is None


def test_termination_is_not_an_expiry():
    assert T.termination("The Board has terminated the tender offer and all tendered shares will be returned.")
    assert T.termination("The Offer terminated at 5:00 p.m., Eastern Time on March 18, 2019, and 7,365,349 shares") is None
    assert T.termination("The tender offer has been withdrawn.")


def test_pricing_rule():
    assert T.pricing_rule("at 98% of NAV as determined on the next business day after the Expiration Date")[0] == "next_bd"
    assert T.pricing_rule("98% of the net asset value per share determined on the Expiration Date")[0] == "expiry"
    assert T.pricing_rule("a price to be set by the Board")[0] is None


def test_joint_release_decided_without_crsp():
    assert T.joint_release_decided_without_crsp("Korea Fund (NYSE: KF) announced", "KF")
    assert T.joint_release_decided_without_crsp("The Malaysia Fund (NYSE: MAY)", None)
    assert not T.joint_release_decided_without_crsp("(NYSE: VLT) and (NYSE: VVR)", "VLT")
    assert not T.joint_release_decided_without_crsp("(NYSE: VLT) and (NYSE: VVR)", None)


# ----------------------------------------------------------------- the 20% gate

def _gate_frame(n, unread, deferred=0):
    rows = []
    for i in range(n):
        u = i < unread
        rows.append({"in_universe": False, "ann_date": pd.Timestamp("2015-01-05"), "merger_open": False,
                     "period": "fit", "outcome": "unread" if u else "completed",
                     "outcome_reason": "unread: pi" if u else None,
                     "pi_how": ("needs CRSP names (joint-release rule)" if (u and i < deferred) else "x")})
    return pd.DataFrame(rows)


def test_dg_nt2_gate():
    assert T.dg_nt2_gate(_gate_frame(134, 26))["verdict"] == "PASS"          # 19.4%
    assert T.dg_nt2_gate(_gate_frame(134, 27))["verdict"] == "FAIL"          # 20.1%
    g = T.dg_nt2_gate(_gate_frame(134, 30, deferred=6))                      # 17.9% .. 22.4%
    assert g["verdict"].startswith("UNDECIDED") and (g["unread_lo"], g["unread_hi"]) == (24, 30)


# ----------------------------------------------------------------- the holdout stays sealed

def test_holdout_refuses_before_a_committed_fit_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "FIT_JSON", tmp_path / "fit.json")
    monkeypatch.setattr(T, "HOLDOUT_JSON", tmp_path / "holdout.json")
    assert not T.fit_verdict_committed()
    with pytest.raises(T.TrialError, match="sealed|committed"):
        T.holdout()
    with pytest.raises(T.TrialError, match="committed"):
        T.holdout_daily([1, 2])


# ----------------------------------------------------------------- a synthetic run end to end

def test_run_pnl_sizes_to_the_vol_target_on_active_sessions():
    from scripts.cef.spec import VOL_TARGET
    S = sessions(300, "2014-01-02")
    rng = np.random.default_rng(3)
    evs = [T.Ev(f"E{i}", f"G{i}", S[20 + 40 * i], S[45 + 40 * i], S[38 + 40 * i], 0.3, 10.5, 1.0, 0.6, "HYG")
           for i in range(6)]
    fund = {e.eid: {"ret": pd.Series(rng.normal(0.0005, 0.01, len(S)), index=S),
                    "close": pd.Series(10.0, index=S)} for e in evs}
    D = T.Data(ev=pd.DataFrame(), fund=fund, etf={"HYG": pd.Series(rng.normal(0, 0.005, len(S)), index=S)},
               sessions=S, factors=None, t_first=S[22], t_last=S[-3])
    run = T.run_pnl(D, evs, None, None)
    assert run["k"] == pytest.approx(VOL_TARGET / run["sigma_active"])
    live = run["trad"]["H"].shift(2).fillna(0).abs().sum(axis=1) > 0
    sized = run["pnl_trad"].loc[S[22]:S[-3]][live.loc[S[22]:S[-3]]]
    assert sized.std() * np.sqrt(252) == pytest.approx(VOL_TARGET, rel=1e-9)
    frozen = T.run_pnl(D, evs, 2.0, None)
    assert frozen["k"] == 2.0


# ----------------------------------------------------------------- Stage 0 part B and the fit, on a synthetic CRSP

def _synthetic_crsp(tmp_path, monkeypatch):
    """A fake CRSP cache (three funds, every hedge ETF, SPY on the NYSE calendar 2016-2022), the
    hedge read, factors and a rulings path, all under tmp_path. Returns the event table."""
    import json as _json
    from scripts.events import crsp_events as ce
    cache = tmp_path / "crsp"
    cache.mkdir()
    monkeypatch.setattr(ce, "CACHE", cache)
    monkeypatch.setattr(T, "CACHE", tmp_path / "trial")
    monkeypatch.setattr(T, "PERMNO_LIST", tmp_path / "trial" / "crsp_permnos.json")
    monkeypatch.setattr(T, "RULINGS", tmp_path / "rulings.csv")
    monkeypatch.setattr(T, "DG4_READS", tmp_path / "dg4.json")
    (tmp_path / "trial").mkdir()
    S = pd.DatetimeIndex([d for d in pd.bdate_range("2016-01-04", "2022-12-30") if T.is_session(d)])
    syms = T.hedge_symbols()
    names = [{"permno": 101 + i, "namedt": pd.Timestamp("2000-01-01"), "nameendt": pd.Timestamp("2024-12-31"),
              "shrcd": 14, "ticker": tk, "comnam": f"{tk} INCOME FUND INC"} for i, tk in enumerate(("AAA", "BBB", "CCC"))]
    names += [{"permno": 900 + i, "namedt": pd.Timestamp("2000-01-01"), "nameendt": pd.Timestamp("2024-12-31"),
               "shrcd": 73, "ticker": s, "comnam": f"{s} ETF"} for i, s in enumerate(syms)]
    names.append({"permno": 999, "namedt": pd.Timestamp("2000-01-01"), "nameendt": pd.Timestamp("2024-12-31"),
                  "shrcd": 14, "ticker": "ZZZ", "comnam": "ZZZ FUND"})
    pd.DataFrame(names).to_parquet(cache / "dsenames.parquet")
    pd.DataFrame({"permno": pd.Series(dtype=int), "dlstdt": pd.Series(dtype="datetime64[ns]"),
                  "dlpdt": pd.Series(dtype="datetime64[ns]"), "nextdt": pd.Series(dtype="datetime64[ns]"),
                  "dlamt": pd.Series(dtype=float), "dlret": pd.Series(dtype=float), "dlretx": pd.Series(dtype=float),
                  "dlprc": pd.Series(dtype=float)}).to_parquet(cache / "dsedelist.parquet")
    monkeypatch.setattr(ce, "universe", lambda: pd.DataFrame({"ticker": ["ZZZ"], "start": ["2005-01-01"]}))
    rng = np.random.default_rng(11)
    etf_r = {900 + i: rng.normal(0, 0.008, len(S)) for i in range(len(syms))}
    rows = []
    for p_, r_ in etf_r.items():
        rows.append(pd.DataFrame({"permno": p_, "date": S, "ret": r_}))
    hyg = etf_r[900 + syms.index("HYG")]
    for i in range(3):
        rows.append(pd.DataFrame({"permno": 101 + i, "date": S, "ret": 0.8 * hyg + rng.normal(0.0002, 0.006, len(S))}))
    dsf = pd.concat(rows, ignore_index=True)
    dsf["retx"] = dsf["ret"]
    dsf["prc"] = 10.0 * (1 + dsf.groupby("permno")["ret"].cumsum())
    dsf["vol"], dsf["shrout"], dsf["cfacpr"] = 1e5, 1e4, 1.0
    plist = sorted(dsf["permno"].unique().tolist())
    _, h = ce._plist(plist)
    dsf.to_parquet(cache / f"dsf_{h}.parquet")
    (tmp_path / "trial" / "crsp_permnos.json").write_text(_json.dumps({"permnos": [int(x) for x in plist]}))
    (tmp_path / "dg4.json").write_text(_json.dumps({
        "alpaca": {"read_utc": "2026-10-19T20:00:00+00:00", "symbols": {s: {"found": True, "shortable": s != "MUB"} for s in syms}},
        "ibkr": {"stamp": "2026-10-19 10:59:08", "date": "2026-10-19",
                 "symbols": {"MUB": {"available": 150000, "fee_rate_pct": 7.73}}}}))
    FD = pd.bdate_range("2008-12-31", "2022-12-30")
    ff = pd.DataFrame({"date": FD, **{c: rng.normal(0, 0.005, len(FD)) for c in ("mktrf", "smb", "hml", "rmw", "cma", "umd")},
                       "rf": 0.0001})
    monkeypatch.setattr(T, "load_ff", lambda: ff.assign(date=pd.to_datetime(ff["date"])))
    ev = []
    for i, (tk, d0, cls) in enumerate((("AAA", "2018-03-05", "high_yield"), ("BBB", "2019-06-03", "high_yield"),
                                       ("CCC", "2021-09-01", "muni"))):
        d0 = pd.Timestamp(d0)
        e0 = T.add_sessions(d0, 1)
        xp = T.add_sessions(d0, 22)
        F = T.add_sessions(xp, 5)
        px_prev = float(dsf.loc[(dsf.permno == 101 + i) & (dsf.date == T.add_sessions(xp, -1)), "prc"].iloc[0])
        ev.append({"event_id": f"ACC{i}", "cik": 1000 + i, "label": tk, "fund": f"{tk} INCOME FUND INC", "ticker": tk,
                   "ticker_now": tk, "sponsor": f"S{i}", "asset_class": cls, "ann_date": d0, "day0": d0,
                   "outcome_session": T.add_sessions(xp, 2), "k_pct": 98.0, "nav": px_prev * 1.05, "nav_date": e0,
                   "entry_session": e0, "x_p": xp, "expiry": xp, "F": F, "last_session": T.add_sessions(F, 1),
                   "outcome": "completed", "pi": 0.3, "p_final": float(dsf.loc[(dsf.permno == 101 + i) & (dsf.date == T.add_sessions(xp, -1)), "prc"].iloc[0]) * 1.02,
                   "period": "fit", "cutoff_ok": True, "in_universe": False, "merger_open": False, "group": f"S{i}@{d0.date()}",
                   "programme": False, "size_pct": 10.0, "dg1": "not flagged", "pi_how": "accepted/tendered", "ann_form": "SC TO-C"})
    return pd.DataFrame(ev), S


def test_stage0_partB_blocks_until_ruled_then_fit_runs(tmp_path, monkeypatch):
    from scripts.events import crsp_events as ce
    ev, S = _synthetic_crsp(tmp_path, monkeypatch)
    names = ce.names()
    flags = pd.DataFrame([{"check": "spec_beta_window", "ticker": "-", "date": "2026-10-19", "period": "all",
                           "event_id": "-", "note": "x"}])
    rec = {}
    with pytest.raises(T.Stage0Halt, match="rulings block"):
        T.stage0_partB(ev, names, flags, rec)
    assert T.RULINGS.exists() and rec["traded_fit"]["events"] == 3 and rec["traded_fit"]["ibkr_routed"] == 1
    R = pd.read_csv(T.RULINGS, dtype=str, keep_default_na=False)
    R["ruling"], R["ruled_by"], R["ruled_on"] = "keep h = 1", "test", "2026-10-19"
    R.to_csv(T.RULINGS, index=False)
    out = T.stage0_partB(ev, names, flags, {})
    D = out["data"]
    assert set(D.ev["etf"]) == {"HYG", "MUB"} and D.ev.loc[D.ev["etf"] == "HYG", "beta"].between(0.6, 1.0).all()
    assert D.ev["adv_usd"].notna().all() and D.ev["disc_post"].notna().all()
    book = pd.Series(np.random.default_rng(5).normal(0, 0.003, len(S)), index=S)
    res = T.fit_on(D, pd.DataFrame(columns=["cik", "kind", "first_date", "last_date"]), 100_000.0, 1.8,
                   placebo_draws=20, quality_ids={"ACC1"}, book=book)
    assert res["verdict"] and set(res["stages"]) == {"1", "2", "3", "4", "5"}
    assert res["stages"]["1"]["n"] == 3 and res["sizing"]["k"] > 0
    assert set(res["grid_tradable"]) >= {"gross", "net5", "net15", "net30", "flips"}
    assert res["borrow_tradable"]["fees_pct"] == {"HYG": 0.0, "MUB": 7.73}
    ro, rb = res["report_only"], res["robustness"]
    assert ro["r_book"]["n"] > 60 and -1 <= ro["r_book"]["corr"] <= 1
    assert ro["capacity"]["events"] == 3 and "at_1000000" in ro["capacity"]
    assert ro["mechanism_slope"]["n"] == 3 and "not computed" in ro["mechanism_slope"]   # fewer than 5 events
    assert 0 <= res["stages"]["2"]["share_draw_means_ge_real"] <= 1
    keys = " | ".join(rb)
    for want in ("residual lag 0", "residual lag 10", "quality-screen events removed (1 removed)", "muni hedged with IEF"):
        assert want in keys
    assert rb["quality-screen events removed (1 removed)"]["per_event"]["n"] == 2


def test_capacity_and_mechanism_slope_arithmetic():
    ev = pd.DataFrame({"eid": ["a", "b", "c", "d", "e", "f"], "adv_usd": [1e6, 2e6, 5e5, 1e6, 3e6, 1e6],
                       "k_pct": 98.0, "disc_post": [-0.05, -0.10, -0.15, -0.08, -0.12, -0.02]})
    evs = [T.Ev(i, i, pd.Timestamp("2015-01-05"), pd.Timestamp("2015-02-05"), None, 0.0, None, 1.0, 1.0, "HYG")
           for i in ev["eid"]]
    w = {i: 0.5 for i in ev["eid"]}
    c = T.capacity(ev, evs, w)
    # median event: ADV 1e6, weight 0.5 -> 1% of ADV at capital 0.01 * 1e6 / 0.5 = 20,000
    assert c["capital_at_1pct_adv_median_event_usd"] == pytest.approx(20_000.0)
    assert c["at_100000"]["participation_median"] == pytest.approx(0.05)
    assert c["at_100000"]["election_fee_bp_of_notional_median"] == pytest.approx(100 / 50_000 * 1e4)
    from scripts.events.cef_corp_action_census import accepted_slice_spread
    spread = np.array([accepted_slice_spread(98.0, d) for d in ev["disc_post"]])
    pe = pd.DataFrame({"eid": ev["eid"], "per_notional": 0.5 * spread + 0.001, "group": list("abcdef")})
    m = T.mechanism_slope(ev, pe)
    assert m["n"] == 6 and m["slope"] == pytest.approx(0.5)


def test_r_book_needs_overlap():
    S = sessions(200)
    x = pd.Series(np.random.default_rng(2).normal(0, 0.01, len(S)), index=S)
    r = T.r_book(x, 2 * x)
    assert r["corr"] == pytest.approx(1.0) and r["beta_on_book"] == pytest.approx(0.5)
    assert "not computed" in T.r_book(x, None)


def test_second_method_agrees_with_the_first_on_synthetic_data(tmp_path, monkeypatch):
    """`rederive` (plain loops, CRSP rows read again) must reproduce fit_on's per-event mean, cluster t
    and both sleeve Sharpes."""
    import json as _json
    from scripts.events import crsp_events as ce
    ev, S = _synthetic_crsp(tmp_path, monkeypatch)
    names = ce.names()
    flags = pd.DataFrame([{"check": "spec_beta_window", "ticker": "-", "date": "2026-10-19", "period": "all",
                           "event_id": "-", "note": "x"}])
    pd.DataFrame([{"check": "spec_beta_window", "ticker": "-", "date": "2026-10-19", "ruling": "keep", "ruled_by": "t",
                   "ruled_on": "2026-10-19"}]).to_csv(T.RULINGS, index=False)
    out = T.stage0_partB(ev, names, flags, {})
    res = T.fit_on(out["data"], pd.DataFrame(columns=["cik", "kind", "first_date", "last_date"]), 100_000.0, 1.8,
                   placebo_draws=5)
    monkeypatch.setattr(T, "FIT_JSON", tmp_path / "fit.json")
    monkeypatch.setattr(T, "TRIAL_DIR", tmp_path)
    T.FIT_JSON.write_text(_json.dumps(T._jsonable(res)))
    monkeypatch.setattr(T, "stage0", lambda **kw: {"data": out["data"]})
    r = T.rederive()
    fm = r["first_method"]
    assert r["per_event_mean"] == pytest.approx(fm["per_event_mean"], rel=1e-9)
    assert r["per_event_cluster_t"] == pytest.approx(fm["per_event_cluster_t"], rel=1e-9)
    assert r["raw_sleeve_sr"] == pytest.approx(fm["raw_sleeve_sr"], rel=1e-9)
    assert r["tradable_sleeve_sr"] == pytest.approx(fm["tradable_sleeve_sr"], rel=1e-9)


def test_holdout_halts_at_its_gate_without_prices(tmp_path, monkeypatch):
    import json as _json
    monkeypatch.setattr(T, "FIT_JSON", tmp_path / "fit.json")
    monkeypatch.setattr(T, "HOLDOUT_JSON", tmp_path / "holdout.json")
    T.FIT_JSON.write_text(_json.dumps({"verdict": "KILL D1"}))
    monkeypatch.setattr(T, "fit_verdict_committed", lambda: True)
    ev = _gate_frame(42, 14).assign(period="holdout", label="X")
    monkeypatch.setattr(T, "stage0", lambda **kw: {"rec": {"gate_holdout_count_only": T.dg_nt2_gate(ev, "holdout")},
                                                   "ev": ev})
    out = T.holdout()
    assert out["verdict"].startswith("HALTED") and T.HOLDOUT_JSON.exists()
    with pytest.raises(T.TrialError, match="opens once"):
        T.holdout()
