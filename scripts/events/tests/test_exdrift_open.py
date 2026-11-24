"""Tests for scripts/events/exdrift_open.py and the opening's gate. Synthetic data only: the
conclusions are about the code (alignment, eligibility, the kill order, the gate), never a market."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from scripts.cef import data_guards as dg
from scripts.events import exdrift_open as xo
from scripts.events import exdrift_trial as x

NAMES = list(x.NAMES)


def _data(drift=-0.002, n=620, seed=1, nav_drift=0.0) -> xo.OpenData:
    """Each fund goes ex every 170 sessions, 10 sessions after the previous fund, so no fund's
    ex-date or drift rows come within 8 sessions of another's: every H-E basket is the 16 others
    and is clean. The event fund's price return is `drift` on each of e+1..e+3, so the short's
    known payoff is -3 * drift per event (0.006 at the default)."""
    rng = np.random.default_rng(seed)
    s = pd.bdate_range("2021-01-04", periods=n)
    R = pd.DataFrame(rng.normal(0, 1e-4, (n, len(NAMES))), index=s, columns=NAMES)
    RN = pd.DataFrame(rng.normal(0, 1e-4, (n, len(NAMES))), index=s, columns=NAMES)
    rows = []
    for j, t in enumerate(NAMES):
        for p in range(15 + 10 * j, n - 12, 170):
            rows.append(dict(ticker=t, ex_date=s[p], declared=s[p - 8], amount=0.1, amount_strata=0.1, special=False))
            R.iloc[p + 1:p + 4, j] += drift
            RN.iloc[p + 1:p + 4, j] += nav_drift
    ex = pd.DataFrame(rows)
    close = pd.DataFrame(10.0, index=s, columns=NAMES)
    F = pd.DataFrame(rng.normal(0, 0.01, (n, 9)), index=s,
                     columns=["mktrf", "smb", "hml", "rmw", "cma", "umd", "TERM", "HY", "MUNI"])
    return xo.OpenData(label="synthetic", sessions=s, R=R, Rpx=R.copy(), RN=RN,
                       masked=pd.DataFrame(False, index=s, columns=NAMES), exdates=ex,
                       candidates=ex[["ticker", "ex_date"]], nav_excluded=set(), close_prev=close,
                       adv63=pd.DataFrame(1e7, index=s, columns=NAMES), factors=F, fee_pct=None,
                       hyg=pd.Series(0.0, index=s), k=0.2, cap=1.8, vol_target=0.06, n_bar=7, window=(s[1], s[-1]),
                       eras=[("all", s[0], s[-1])], core13=tuple(x.CORE), munis=tuple(x.MUNIS))


def test_per_event_pnl_is_the_known_payoff_and_sums_to_evaluate():
    D = _data()
    out = xo.open_core(D)
    ev = out["events"]
    assert len(ev) > 0
    assert ev.nb.min() == len(NAMES) - 1                   # every basket is the 16 others
    assert ev.x.mean() == pytest.approx(0.006, abs=2e-4)
    assert out["report"]["stage1_event_mean"]["pass"]


def test_the_basket_excludes_funds_declared_ex_in_e_plus_1_to_8_and_keeps_undeclared():
    D = _data()
    decl = xo.own_declared(D)
    sp = {d: i for i, d in enumerate(D.sessions)}
    r = D.exdates.iloc[0]
    p = sp[r.ex_date]
    b = xo.basket_for(D, r.ticker, p, decl)
    for j in b:
        assert not any(1 <= q - p <= 8 and dd <= D.sessions[p - 1] for q, dd in decl.get(j, []))
    D2 = _data()
    D2.exdates["declared"] = pd.NaT                         # nothing declared: R10 keeps every fund
    b2 = xo.basket_for(D2, r.ticker, p, xo.own_declared(D2))
    assert len(b2) == len(NAMES) - 1


def test_rule1_excludes_an_event_declared_after_e_minus_1():
    D = _data()
    sp = {d: i for i, d in enumerate(D.sessions)}
    i0 = D.exdates.index[0]
    D.exdates.loc[i0, "declared"] = D.sessions[sp[D.exdates.loc[i0, "ex_date"]]]   # declared on e
    _, n = xo.build_events(D)
    assert n["rule1_not_declared"] == 1


def test_a_nav_leg_that_moves_with_the_price_kills_stage_3():
    out = xo.open_core(_data(nav_drift=-0.002))
    assert not out["report"]["stage3_nav_leg"]["pass"]
    assert out["report"]["verdict"].startswith("KILL (NAV leg")


def test_no_drift_kills_stage_1_first():
    out = xo.open_core(_data(drift=0.0))
    assert out["report"]["verdict"] == "KILL D1"


def test_placebo_events_never_hold_near_a_real_ex_date():
    D = _data()
    ev, _ = xo.build_events(D)
    own = xo.own_ex_positions(D)
    for sh in (5, -10):
        pe, _ = xo.build_events(D, shift=sh, real=ev[["ticker", "ex_date"]])
        for t, p in zip(pe.ticker, pe.p):
            assert not any(abs(p + k - q) <= 3 for q in own[t] for k in (1, 2, 3))


def test_control_kills_rule():
    assert xo.control_kills(12.0, 20.0) and not xo.control_kills(9.9, 20.0)
    assert not xo.control_kills(-15.0, 20.0)


def test_a_held_cell_without_a_return_raises():
    D = _data()
    out = xo.open_core(D)
    t, p = out["events"].iloc[0][["ticker", "p"]]
    b = out["events"].iloc[0].basket.split(",")[0]
    D.R.iloc[p + 2, D.R.columns.get_loc(b)] = np.nan       # a basket leg loses a hold-row return after selection
    with pytest.raises(xo.OpenError):
        xo.sleeve(D, out["events"])


def test_a_factor_gap_is_a_halt_not_a_kill():
    D = _data()
    D.factors.iloc[-5:] = np.nan
    with pytest.raises(xo.OpenError, match="HALT"):
        xo.open_core(D)


def test_an_unmeasurable_control_is_a_halt():
    with pytest.raises(xo.OpenError, match="HALT"):
        xo.control_kills(float("nan"), 20.0)


def test_rule3_split_mask_is_counted_apart_from_rule4():
    D = _data()
    sp = {d: i for i, d in enumerate(D.sessions)}
    r = D.exdates.iloc[0]
    D.masked.iloc[sp[r.ex_date] + 2, D.masked.columns.get_loc(r.ticker)] = True
    _, n = xo.build_events(D)
    assert n["rule3_split_mask"] == 1


def test_the_r10_alternative_is_reported_beside():
    out = xo.open_core(_data())
    assert out["report"]["report_only"]["R10_alternative_basket"]["unknown"] == "exclude"


def test_d4_betas_are_scaled_to_the_vol_target():
    out = xo.open_core(_data())
    d4 = out["report"]["stage5_d4"]
    c = "mktrf"
    assert d4["betas_summed_at_target"][c] == pytest.approx(d4["betas_summed_raw"][c] * d4["scale_to_vol_target"])


def test_load_test_refuses_without_the_gate_token():
    with pytest.raises(xo.OpenError, match="token"):
        xo.load_test(None, 0.16, 1.8, 0.06, 7, (None, None))


# --------------------------------------------------------------------------- the gate

def _clear(tmp_path, stage0="CLEAR", go="2026-10-28"):
    F = pd.DataFrame([{"check": "R1", "ticker": "-", "date": "2026-10-27", "gate": "DG-X4", "events": "-",
                       "note": "n", "recommended": "r"}])
    fp, rp, rec, k = tmp_path / "f.csv", tmp_path / "r.csv", tmp_path / "rec.json", tmp_path / "k.json"
    F.to_csv(fp, index=False)
    x.apply_rulings(fp, rp)
    rec.write_text(json.dumps({"stage0": stage0, "gates": {}, "dg_x1_refresh": {"test_end_ex": "2026-10-12"}}))
    k.write_text(json.dumps({"k": 0.16, "cap": 1.8}))
    o = tmp_path / "open_rulings.csv"
    rows = [dict(check=c, ticker="-", date="2026-10-28", ruling="as written", ruled_by="team lead", ruled_on="2026-10-28")
            for c, _ in x.OPEN_READINGS] + [dict(check="GO", ticker="-", date="2026-10-28", ruling="GO", ruled_by="team lead",
                                                 ruled_on=go)]
    pd.DataFrame(rows).to_csv(o, index=False)
    return dict(flags_path=fp, rulings_path=rp, record=rec, k_path=k), o


@pytest.fixture
def quiet_gate(monkeypatch):
    monkeypatch.setattr(x, "sessions_calendar", lambda: pd.bdate_range("2023-01-02", "2026-10-30"))
    monkeypatch.setattr(x, "factor_gaps", lambda w, s: [])
    monkeypatch.setattr(x, "open_preconditions", lambda rec: [])


def _gate(tmp_path, go, P, o, **kw):
    return x.open_gate(go, check_git=False, opened=tmp_path / "o.json", open_rulings=o, verify_pins=False, **P, **kw)


def test_open_refuses_without_an_explicit_go_or_with_a_future_one(tmp_path, quiet_gate):
    P, o = _clear(tmp_path)
    with pytest.raises(dg.Stage0BlockError, match="team-lead-go"):
        _gate(tmp_path, None, P, o)
    with pytest.raises(dg.Stage0BlockError, match="future"):
        _gate(tmp_path, "2999-01-01", P, o)
    with pytest.raises(dg.Stage0BlockError, match="not a date"):
        _gate(tmp_path, "tomorrow", P, o)


def test_open_needs_the_go_row_and_every_open_reading_ruled(tmp_path, quiet_gate):
    P, o = _clear(tmp_path, go="2026-10-27")
    with pytest.raises(dg.Stage0BlockError, match="GO row"):
        _gate(tmp_path, "2026-10-28", P, o)
    P, o = _clear(tmp_path)
    O = pd.read_csv(o, dtype=str, keep_default_na=False)
    O.loc[O.check == "O2", "ruling"] = ""
    O.to_csv(o, index=False)
    with pytest.raises(dg.Stage0BlockError, match="O2"):
        _gate(tmp_path, "2026-10-28", P, o)
    P, o = _clear(tmp_path)
    gd, k, _, window, token = _gate(tmp_path, "2026-10-28", P, o)
    assert token is xo._GATE_TOKEN and k["k"] == 0.16
    assert window[1] == pd.Timestamp("2026-10-09")            # O1 as ruled: where IEF and HYG end


def test_open_refuses_a_second_opening_and_a_halted_record(tmp_path, quiet_gate):
    P, o = _clear(tmp_path)
    (tmp_path / "o.json").write_text("{}")
    with pytest.raises(dg.Stage0BlockError, match="opened once"):
        _gate(tmp_path, "2026-10-28", P, o)
    (tmp_path / "o.json").unlink()
    P["record"].write_text(json.dumps({"stage0": "HALTED", "gates": {}, "dg_x1_refresh": {"test_end_ex": "2026-10-12"}}))
    with pytest.raises(dg.Stage0BlockError, match="HALTED"):
        _gate(tmp_path, "2026-10-28", P, o)


def test_open_refuses_inputs_that_changed_after_stage0(tmp_path, quiet_gate, monkeypatch):
    P, o = _clear(tmp_path)
    f = tmp_path / "panel.bin"
    f.write_bytes(b"as pinned")
    monkeypatch.setattr(x, "PINNED", {"prices": f})
    import hashlib
    rec = json.loads(P["record"].read_text())
    rec["input_pins_sha256"] = {"prices": hashlib.sha256(b"as pinned").hexdigest()}
    P["record"].write_text(json.dumps(rec))
    x.open_gate("2026-10-28", check_git=False, opened=tmp_path / "o.json", open_rulings=o, **P)
    f.write_bytes(b"refreshed since")
    with pytest.raises(dg.Stage0BlockError, match="pinned"):
        x.open_gate("2026-10-28", check_git=False, opened=tmp_path / "o.json", open_rulings=o, **P)


def test_open_refuses_a_factor_gap_in_the_window(tmp_path, quiet_gate, monkeypatch):
    P, o = _clear(tmp_path)
    monkeypatch.setattr(x, "factor_gaps", lambda w, s: ["IEF misses 4 session(s)"])
    with pytest.raises(dg.Stage0BlockError, match="IEF"):
        _gate(tmp_path, "2026-10-28", P, o)


def test_factor_gaps_reads_presence_on_the_window_and_the_lag_row(tmp_path, monkeypatch):
    s = pd.bdate_range("2026-09-01", "2026-10-15")
    ff = tmp_path / "ff.parquet"
    pd.DataFrame({"date": s[s <= "2026-09-30"], **{c: 0.0 for c in ("mktrf", "smb", "hml", "rmw", "cma", "umd", "rf")}}).to_parquet(ff)
    et = tmp_path / "etf.parquet"
    pd.concat([pd.DataFrame({"date": s, "ticker": t, "ret_total": 0.0}) for t in ("IEF", "HYG")]).to_parquet(et)
    mb = tmp_path / "mub.parquet"
    pd.DataFrame({"date": s, "close": 100.0}).to_parquet(mb)
    monkeypatch.setattr(x, "FF_DAILY", ff)
    monkeypatch.setattr(x, "ETF_DAILY", et)
    monkeypatch.setattr(x, "ETF_YF", {"MUB": mb})
    g = x.factor_gaps((s[5], s[-1]), s)
    assert len(g) == 1 and g[0].startswith("French")


def test_power_at_reproduces_the_preregistration_at_its_own_count():
    p = x.power_at(714, 537, 45, 950)
    assert p["event_17_1.0"]["p_t_ge_2"] == pytest.approx(0.94, abs=0.01)
    assert p["event_13_1.0"]["p_t_ge_2"] == pytest.approx(0.86, abs=0.01)
    assert p["sleeve_1.0"]["sr"] == pytest.approx(1.78, abs=0.01)


# --------------------------------------------------------------------------- amendment 1: the MUB/IEF hedge

def test_hedge_betas_recover_known_loadings_and_the_hedge_offsets_them():
    rng = np.random.default_rng(3)
    s = pd.bdate_range("2010-01-04", periods=1500)
    F = pd.DataFrame(rng.normal(0, 0.005, (len(s), len(x.D4_FACTORS))), index=s, columns=list(x.D4_FACTORS))
    R = pd.DataFrame({"AAA": 1.2 * F.MUNI + 0.5 * F.TERM + rng.normal(0, 1e-4, len(s)),
                      "BBB": 0.2 * F.MUNI + 1.5 * F.TERM.shift(1).fillna(0) + rng.normal(0, 1e-4, len(s))}, index=s)
    b = x.hedge_betas_core(R, F)
    assert b["AAA"]["beta_MUNI"] == pytest.approx(1.2, abs=0.01) and b["BBB"]["beta_TERM"] == pytest.approx(1.5, abs=0.01)
    hM, hI = x.hedge_weights("AAA", ["BBB"], b)
    eM, eT = -1.2 + 0.2, -0.5 + 1.5
    assert hM == pytest.approx(-eM, abs=0.02) and hI == pytest.approx(eM - eT, abs=0.02)
    # holding hM of MUB = MUNI + IEF and hI of IEF = TERM + RF adds hM to MUNI and hM + hI to TERM
    assert hM + eM == pytest.approx(0, abs=0.02) and (hM + hI) + eT == pytest.approx(0, abs=0.03)


def test_the_hedge_enters_the_event_pnl_and_the_sleeve_sums_to_it():
    D = _data()
    D.hedge_betas = {t: {"beta_MUNI": 0.1 * i, "beta_TERM": 1.0 + 0.05 * i} for i, t in enumerate(NAMES)}
    rng = np.random.default_rng(7)
    D.hedge_R = pd.DataFrame(rng.normal(0, 0.003, (len(D.sessions), 2)), index=D.sessions, columns=["MUB", "IEF"])
    ev, _ = xo.build_events(D)
    r = ev.iloc[0]
    hold = [r.p + 1, r.p + 2, r.p + 3]
    want = r.x_unhedged + float((D.hedge_R.to_numpy()[hold] @ np.array([r.h_MUB, r.h_IEF])).sum())
    assert r.x == pytest.approx(want)
    S = xo.sleeve(D, ev)                       # asserts the per-event sum equals evaluate()'s P&L
    assert {"MUB", "IEF"} <= set(S["H"].columns)


def test_a_missing_hedge_return_is_a_halt():
    D = _data()
    D.hedge_betas = {t: {"beta_MUNI": 0.5, "beta_TERM": 1.0} for t in NAMES}
    D.hedge_R = pd.DataFrame(0.0, index=D.sessions, columns=["MUB", "IEF"])
    D.hedge_R.iloc[:, 0] = np.nan
    with pytest.raises(xo.OpenError, match="HALT"):
        xo.build_events(D)


def test_o1_window_ends_on_2026_10_09():
    s = pd.bdate_range("2023-01-02", "2026-10-30")
    w = x.pnl_window({"dg_x1_refresh": {"test_end_ex": "2026-10-12"}}, s)
    assert w[1] == pd.Timestamp("2026-10-09")
