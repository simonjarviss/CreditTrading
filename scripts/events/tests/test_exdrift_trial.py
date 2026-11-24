"""Tests for scripts/events/exdrift_trial.py (EVENTS trial 3, Stage 0). Synthetic data only.

The conclusions are about our code (the gates, the block, the date arithmetic), never about a market.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from scripts.cef import data_guards as dg
from scripts.events import exdrift_trial as x


def _sessions(start="2024-01-02", n=60):
    return pd.bdate_range(start, periods=n)


# --------------------------------------------------------------------------- constants pinned to their owners

def test_constants_pinned_to_their_owners():
    import scripts.cef.spec as spec
    from scripts.cef.band_frontier import HOLDOUT_START
    from scripts.cef.c4_families import DIV_TOL
    assert x.TEST_START == HOLDOUT_START
    assert x.DIV_TOL == DIV_TOL
    assert x.CORE == tuple(spec.UNIVERSE) and len(x.NAMES) == 17 and len(set(x.NAMES)) == 17
    assert set(x.NAMES) - set(x.CORE) == {"NAD", "NEA", "NVG", "NZF"}
    assert x.N_BAR == 7


def test_every_reading_is_a_flag_with_a_gate():
    codes = [r[0] for r in x.READINGS]
    assert codes == [f"R{i}" for i in range(1, len(codes) + 1)]
    assert all(r[1] in x.GATES and r[2] and r[3] for r in x.READINGS)


# --------------------------------------------------------------------------- the sealed names

def test_only_names_refuses_a_sealed_name():
    with pytest.raises(x.Stage0Error, match="outside the 17"):
        x._only_names(pd.DataFrame({"ticker": ["PTY", "XYZ"]}), "probe")


def test_present_keeps_booleans_and_never_loads_other_names(tmp_path):
    p = tmp_path / "px.parquet"
    d = pd.DataFrame({"date": pd.to_datetime(["2022-12-30", "2023-01-03", "2023-01-04", "2023-01-03"]),
                      "ticker": ["PTY", "PTY", "PTY", "SEALED"], "close": [10.0, np.nan, 0.0, 5.0]})
    d.to_parquet(p, index=False)
    s = pd.DatetimeIndex(["2022-12-30", "2023-01-03", "2023-01-04"])
    ok = x._present(p, "close", s, test="notna")
    assert ok.dtypes.eq(bool).all() and "SEALED" not in ok.columns
    assert not ok.at[pd.Timestamp("2022-12-30"), "PTY"]          # the fit row is never read
    assert not ok.at[pd.Timestamp("2023-01-03"), "PTY"] and ok.at[pd.Timestamp("2023-01-04"), "PTY"]
    z = x._present(p, "close", s, test="zero")
    assert z.at[pd.Timestamp("2023-01-04"), "PTY"] and not z.at[pd.Timestamp("2023-01-03"), "PTY"]


def test_present_repeat_flags_equal_consecutive_values(tmp_path):
    p = tmp_path / "nav.parquet"
    pd.DataFrame({"date": pd.to_datetime(["2023-01-03", "2023-01-04", "2023-01-05"]), "ticker": "NAD",
                  "nav": [11.0, 11.0, 11.01]}).to_parquet(p, index=False)
    s = pd.DatetimeIndex(["2023-01-03", "2023-01-04", "2023-01-05"])
    r = x._present(p, "nav", s, test="repeat")
    assert list(r["NAD"]) == [False, True, False]


def test_read_fit_never_loads_a_test_row(tmp_path):
    p = tmp_path / "f.parquet"
    pd.DataFrame({"date": pd.to_datetime(["2022-12-30", "2023-01-03"]), "ticker": "PTY", "close": [1.0, 2.0]}
                 ).to_parquet(p, index=False)
    d = x.read_fit(p, ["date", "ticker", "close"])
    assert d["date"].max() <= x.FIT_END and len(d) == 1


# --------------------------------------------------------------------------- DG-X7 machinery

def test_fit_returns_refuses_a_test_row():
    idx = pd.DatetimeIndex(["2022-12-29", "2023-01-03"])
    with pytest.raises(x.Stage0Error):
        x.fit_returns(pd.DataFrame({"PTY": [1.0, 1.0]}, index=idx),
                      pd.DataFrame(columns=["ticker", "ex_date", "amount", "stock_split"]))


def test_r6_events_car_is_the_abnormal_sum_over_three_rows():
    idx = pd.bdate_range("2010-01-04", periods=40)
    ret = pd.DataFrame(0.0, index=idx, columns=list(x.NAMES))
    i = 20
    ret.iloc[i + 1:i + 4, ret.columns.get_loc("PTY")] = -0.01
    dist = pd.DataFrame({"ticker": ["PTY"], "ex_date": [idx[i]], "amount": [0.1], "stock_split": [0.0]})
    ev = x.r6_events(ret, dist)
    assert len(ev) == 1
    assert ev["car13"].iloc[0] == pytest.approx(3 * -0.01 * (16 / 17))


def test_he_basket_excludes_funds_with_an_own_ex_date_in_e_plus_1_to_8():
    idx = pd.bdate_range("2010-01-04", periods=40)
    ret = pd.DataFrame(0.0, index=idx, columns=list(x.NAMES))
    i = 20
    others = [n for n in x.NAMES if n != "PTY"]
    late = others[:3]                                 # an own ex-date at e+8: out
    dist = pd.DataFrame({"ticker": ["PTY"] + late, "ex_date": [idx[i]] + [idx[i + 8]] * 3, "amount": 0.1,
                         "stock_split": 0.0})
    E = x.he_events(ret, dist)
    row = E[E.ticker == "PTY"].iloc[0]
    assert row.nb == len(others) - 3


def test_assert_denormal_free():
    x.assert_denormal_free([0.0, 1e-3, -2.0])
    with pytest.raises(AssertionError):
        x.assert_denormal_free([1e-310])


# --------------------------------------------------------------------------- the test calendar

def test_test_end_is_the_earlier_of_the_two():
    s = _sessions()
    assert x.test_end(s[-1], s, s[-1]) == s[-1 - x.HOLD]
    assert x.test_end(s[10], s, s[-1]) == s[10]


def test_test_events_rules_2_and_3_and_non_sessions():
    s = _sessions("2023-01-02", 60)
    dist = pd.DataFrame({"ticker": ["PTY", "PTY", "BIT", "PDI"],
                         "ex_date": [s[10], s[12], s[30], pd.Timestamp("2023-01-07")],   # a Saturday
                         "amount": 0.1, "stock_split": 0.0})
    splits = pd.DataFrame({"ticker": ["BIT"], "ex_date": [s[36]], "stock_split": [1.029]})
    ev, ns = x.test_events(dist, s, s[-5], splits)
    e = ev.set_index(["ticker", "ex_date"])
    assert bool(e.loc[("PTY", s[10]), "next_ex_within3"]) and not bool(e.loc[("PTY", s[12]), "next_ex_within3"])
    assert bool(e.loc[("BIT", s[30]), "split_masked"])       # rows 31..33 lie within 5 of 36
    assert list(ns.ticker) == ["PDI"]


def test_split_basis_class_agrees_with_the_guard():
    assert x.split_basis_class(1.029) == "undecidable"
    assert x.split_basis_class(3.0) == "needs_return"
    idx = pd.DatetimeIndex(["2025-08-19"])
    for r in (-0.05, 0.0, 0.04):
        C = dg.split_basis_check(pd.DataFrame({"BIT": [r]}, index=idx), pd.DataFrame({"BIT": [1.029]}, index=idx))
        assert C["basis"].iloc[0] == "undecidable"


def test_calendar_basket_needs_bars_and_no_own_ex_in_window():
    s = _sessions("2023-01-02", 40)
    p = 10
    dist = pd.DataFrame({"ticker": ["PTY", "PDI"], "ex_date": [s[p], s[p + 8]], "amount": 0.1, "stock_split": 0.0})
    ev = pd.DataFrame({"ticker": ["PTY"], "ex_date": [s[p]], "p": [p]})
    ok = pd.DataFrame(True, index=s, columns=list(x.NAMES))
    ok.loc[s[p + 2], "PHK"] = False
    n = x.calendar_baskets(ev, dist, s, ok, pd.DataFrame(columns=["ticker", "ex_date", "stock_split"]))
    assert n.iloc[0] == 17 - 1 - 2                     # not PTY itself, not PDI (ex at e+8), not PHK (no bar)


# --------------------------------------------------------------------------- DG-X1..X3

def test_yf_vs_alpaca_agree_mismatch_and_absence():
    s = _sessions("2025-01-02", 30)
    ev = pd.DataFrame({"ticker": ["PTY"], "ex_date": [s[5]], "p": [5]})
    yf = pd.DataFrame({"ticker": ["PTY", "PDI", "PHK"], "ex_date": [s[5], s[6], s[7]], "amount": [0.1030, 0.2, 0.05],
                       "stock_split": 0.0})
    alp = pd.DataFrame({"kind": ["cash_dividends", "capital_gains_distributions", "cash_dividends", "cash_dividends"],
                        "ticker": ["PTY", "PTY", "PDI", "PFN"], "ex_date": [s[5], s[5], s[6], s[8]],
                        "amount": [0.1, 0.0035, 0.21, 0.07]})
    rows, st = x.yf_vs_alpaca(ev, yf, alp, s[-1])
    got = {(r["check"], r["ticker"]) for r in rows}
    assert got == {("X1_amount_mismatch", "PDI"), ("X1_alpaca_absent", "PHK"), ("X1_yf_absent", "PFN")}
    assert st["agree"] == 1                             # PTY: 0.1 + 0.0035 = 0.1035 vs 0.1030, within DIV_TOL


def test_record_flags_follow_the_settlement_regimes():
    s = pd.DatetimeIndex(pd.bdate_range("2024-05-01", "2024-06-28"))
    p2 = s.get_loc(pd.Timestamp("2024-05-23"))
    p1 = s.get_loc(pd.Timestamp("2024-06-03"))
    ev = pd.DataFrame({"ticker": ["PTY", "PDI", "PHK", "PCN", "PFN"],
                       "ex_date": [s[p2], s[p2], s[p1], s[p1], s[p1]], "p": [p2, p2, p1, p1, p1]})
    alp = pd.DataFrame({"kind": "cash_dividends", "ticker": ["PTY", "PDI", "PHK", "PCN"],
                        "ex_date": [s[p2], s[p2], s[p1], s[p1]],
                        "record_date": [s[p2 + 1], s[p2], s[p1], s[p1 + 1]]})
    rows, st = x.record_flags(ev, alp, s)
    got = {(r["check"], r["ticker"]) for r in rows}
    assert got == {("X3_regime_break", "PDI"), ("X3_regime_break", "PCN"), ("X3_no_record_date", "PFN")}
    assert st["regime_ok"] == 2


def test_declaration_flags_e_minus_1_passes_e_fails():
    s = _sessions("2025-03-03", 30)
    p = 10
    ev = pd.DataFrame({"ticker": ["PTY", "PDI", "PHK", "PCN"], "ex_date": [s[p]] * 4, "p": [p] * 4})
    ann = pd.DataFrame({"status": 200, "ticker": ["PTY", "PDI", "PHK"], "ex_date": [s[p]] * 3,
                        "declaration_date": [s[p - 1], s[p], s[p - 5]]})
    rows, st = x.declaration_flags(ev, ann, s)
    got = {(r["check"], r["ticker"]) for r in rows}
    assert got == {("X2_declared_late", "PDI"), ("X2_no_declaration", "PCN")}
    assert st == {"declared_by_e_minus_1": 2, "declared_on_e_minus_1": 1, "declared_by_e_minus_2": 1}


# --------------------------------------------------------------------------- DG-X4, DG-X5

def test_bar_and_nav_flags_on_the_event_fund():
    s = _sessions("2026-02-02", 20)
    p = 5
    ev = pd.DataFrame({"ticker": ["PTY"], "ex_date": [s[p]], "p": [p]})
    ok = pd.DataFrame(True, index=s, columns=list(x.NAMES))
    vz = pd.DataFrame(False, index=s, columns=list(x.NAMES))
    ok.loc[s[p], "PTY"] = False                        # no close on e
    vz.loc[s[p + 3], "PTY"] = True                     # zero volume on the cover day, close present
    vz.loc[s[p + 1], "PTY"] = True                     # not a fill day: not flagged
    ok.loc[s[p + 1], "PDI"] = False                    # a basket fund: not flagged (R5)
    rows = x.bar_flags(ev, s, ok, vz, pd.DataFrame({"ticker": ["PTY"], "date": [s[p]], "close": [10.0], "volume": [0.0]}))
    got = {(r["check"], r["date"]) for r in rows}
    assert got == {("X4_no_bar", str(s[p].date())), ("X4_zero_volume_fill", str(s[p + 3].date()))}
    note = [r for r in rows if r["check"] == "X4_no_bar"][0]["note"]
    assert "Alpaca raw SIP bar present: close yes, volume > 0 no" in note
    nok = pd.DataFrame(True, index=s, columns=list(x.NAMES))
    nrp = pd.DataFrame(False, index=s, columns=list(x.NAMES))
    nrp.loc[s[p], "PTY"] = True                        # a repeat on e: the stale cum-distribution NAV, its own class
    nrp.loc[s[p + 2], "PTY"] = True
    nok.loc[s[p + 3], "PTY"] = False
    n = x.nav_flags(ev, s, nok, nrp)
    assert {(r["check"], r["date"]) for r in n} == {("X5_nav_repeat", str(s[p + 2].date())),
                                                     ("X5_nav_missing", str(s[p + 3].date())),
                                                     ("X5_nav_repeat_on_e", str(s[p].date()))}


def test_missing_close_cells_counts_own_ex_dates():
    s = _sessions("2026-02-02", 10)
    ok = pd.DataFrame(True, index=s, columns=list(x.NAMES))
    ok.loc[s[3], "PTY"] = False
    ok.loc[s[4], "PDI"] = False
    dist = pd.DataFrame({"ticker": ["PTY"], "ex_date": [s[3]]})
    m = x.missing_close_cells(ok, s, dist)
    assert m["cells"] == 2 and m["on_own_ex_date"] == 1


# --------------------------------------------------------------------------- the block

def _flags(tmp_path):
    F = pd.DataFrame([{"check": "X4_no_bar", "ticker": "PTY", "date": "2026-02-12", "gate": "DG-X4", "events": "-",
                       "note": "n", "recommended": "r"},
                      {"check": "R1", "ticker": "-", "date": "2026-10-27", "gate": "DG-X4", "events": "-",
                       "note": "n", "recommended": "r"}])
    p = tmp_path / "flags.csv"
    F.to_csv(p, index=False)
    return F, p


def test_block_refuses_while_any_flag_lacks_a_ruling(tmp_path):
    F, fp = _flags(tmp_path)
    rp = tmp_path / "rulings.csv"
    with pytest.raises(dg.Stage0BlockError, match="no rulings file"):
        x.require_stage0_rulings_only(fp, rp, check_git=False)
    dg.stage0_rulings_template(F, rp)
    with pytest.raises(dg.Stage0BlockError, match="lack a recorded ruling"):
        x.require_stage0_rulings_only(fp, rp, check_git=False)
    R = pd.read_csv(rp, dtype=str, keep_default_na=False)
    R.loc[0, ["ruling", "ruled_by", "ruled_on"]] = ["fill from Alpaca", "team lead", "2026-10-28"]
    R.to_csv(rp, index=False)
    with pytest.raises(dg.Stage0BlockError, match="1 of 2"):
        x.require_stage0_rulings_only(fp, rp, check_git=False)
    R.loc[1, ["ruling", "ruled_by", "ruled_on"]] = ["keep", "team lead", "2026-10-28"]
    R.to_csv(rp, index=False)
    J = x.require_stage0_rulings_only(fp, rp, check_git=False)
    assert len(J) == 2


def test_open_needs_a_clear_record_and_a_committed_k(tmp_path):
    F, fp = _flags(tmp_path)
    rp = tmp_path / "rulings.csv"
    dg.stage0_rulings_template(F, rp)
    R = pd.read_csv(rp, dtype=str, keep_default_na=False)
    R[["ruling", "ruled_by", "ruled_on"]] = ["keep", "team lead", "2026-10-28"]
    R.to_csv(rp, index=False)
    rec, k = tmp_path / "rec.json", tmp_path / "k.json"
    rec.write_text(json.dumps({"stage0": "HALTED", "gates": {"DG-X2": "AWAITING TEAM LEAD"}}))
    with pytest.raises(dg.Stage0BlockError, match="HALTED"):
        x.require_stage0_clear(fp, rp, rec, k, check_git=False)
    rec.write_text(json.dumps({"stage0": "CLEAR", "gates": {}}))
    with pytest.raises(dg.Stage0BlockError, match="fit-k"):
        x.require_stage0_clear(fp, rp, rec, k, check_git=False)
    k.write_text("{}")
    assert len(x.require_stage0_clear(fp, rp, rec, k, check_git=False)) == 2


def test_later_stages_refuse_without_a_stage0_record(tmp_path, monkeypatch):
    monkeypatch.setattr(x, "FLAGS", tmp_path / "none.csv")
    with pytest.raises(dg.Stage0BlockError, match="stage0"):
        x.require_stage0_rulings_only(x.FLAGS, tmp_path / "r.csv", check_git=False)


def test_a_blank_form_is_not_a_record_but_a_ruled_one_is(tmp_path):
    F, _ = _flags(tmp_path)
    rp = tmp_path / "rulings.csv"
    dg.stage0_rulings_template(F, rp)
    assert x._blank_form(rp)
    R = pd.read_csv(rp, dtype=str, keep_default_na=False)
    R.loc[0, "ruling"] = "keep"
    R.to_csv(rp, index=False)
    assert not x._blank_form(rp)


def test_declaration_field_check_finds_a_contradicting_notice():
    ann = pd.DataFrame({"status": 200, "ticker": ["PTY", "PDI"], "ex_date": pd.to_datetime(["2025-10-14"] * 2),
                        "declaration_date": pd.to_datetime(["2025-10-12", "2025-10-01"]),
                        "record_date": pd.to_datetime(["2025-10-14"] * 2)})
    N = pd.DataFrame({"ticker": ["PTY", "PDI"], "ex_date": pd.to_datetime(["2025-10-14"] * 2),
                      "stated_declaration": pd.to_datetime(["2025-10-01"] * 2)})
    c = x.declaration_field_check(ann, N)
    assert c["notices_contradict"] == 1 and c["notices_agree"] == 1
    assert c["record_minus_declaration_weekdays"] == {1: 1, 9: 1}


def test_verify_notices_refuses_a_quote_its_document_lacks(tmp_path):
    cache = tmp_path / "c"
    cache.mkdir()
    url = "https://example.org/n.html"
    (cache / "abc.bin").write_bytes(b"<p>NEW YORK, October 1, 2025. Record October 14, 2025 (NYSE: PTY)</p>")
    (cache / "manifest.json").write_text(json.dumps({url: "abc"}))
    p = tmp_path / "n.csv"
    pd.DataFrame([{"ticker": "PTY", "ex_date": "2025-10-14", "stated_declaration": "2025-10-01", "url": url,
                   "quote_declared": "NEW YORK, October 1, 2025", "quote_dates": "Record October 14, 2025",
                   "quote_fund": "(NYSE: PTY)"}]).to_csv(p, index=False)
    assert len(x.verify_notices(p, cache)) == 1
    pd.DataFrame([{"ticker": "PTY", "ex_date": "2025-10-14", "stated_declaration": "2025-10-01", "url": url,
                   "quote_declared": "NEW YORK, October 2, 2025", "quote_dates": "Record October 14, 2025",
                   "quote_fund": "(NYSE: PTY)"}]).to_csv(p, index=False)
    with pytest.raises(x.Stage0Error, match="not found"):
        x.verify_notices(p, cache)


# --------------------------------------------------------------------------- the rulings and fit-k

def test_every_flag_class_has_a_ruling_or_raises():
    assert "excluded and counted" in x.ruling_for("X2_not_found", "-")
    assert "book as is" in x.ruling_for("X5_nav_repeat", "2025-01-15 (e+1)")
    assert "NAV leg" in x.ruling_for("X5_nav_repeat", "2025-01-15 (e+3)")
    with pytest.raises(x.Stage0Error):
        x.ruling_for("X5_nav_repeat", "2025-01-15 (e+1); 2025-02-14 (e+3)")
    with pytest.raises(x.Stage0Error):
        x.ruling_for("X9_unknown", "-")
    for code, *_ in x.READINGS:
        assert x.ruling_for(code, "-")


def test_apply_rulings_fills_every_row_and_never_rewrites_a_different_record(tmp_path):
    F, fp = _flags(tmp_path)
    rp = tmp_path / "r.csv"
    dg.stage0_rulings_template(F, rp)
    R = x.apply_rulings(fp, rp)
    assert (R.ruled_by == "team lead").all() and (R.ruled_on == "2026-10-28").all()
    assert len(x.require_stage0_rulings_only(fp, rp, check_git=False)) == 2
    x.apply_rulings(fp, rp)                                   # identical: allowed
    old = pd.read_csv(rp, dtype=str, keep_default_na=False)
    old.loc[0, "ruling"] = "something else"
    old.to_csv(rp, index=False)
    with pytest.raises(dg.Stage0BlockError, match="would change"):
        x.apply_rulings(fp, rp)
    R2 = x.apply_rulings(fp, rp, supersede=("R1",))           # the team lead re-ruled that class
    assert R2.loc[R2.check == "R1", "ruling"].iloc[0] == x.ruling_for("R1", "-")


def _fit_panel(seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2010-01-04", periods=200)
    ret = pd.DataFrame(rng.normal(0, 0.01, (len(idx), len(x.NAMES))), index=idx, columns=list(x.NAMES))
    ex = [idx[i] for i in (20, 60, 100, 140)]
    dist = pd.DataFrame({"ticker": "PTY", "ex_date": ex, "amount": 0.1, "stock_split": 0.0})
    return ret, dist


def test_fit_k_core_scales_to_the_vol_target_and_counts_cap_binding():
    ret, dist = _fit_panel()
    out = x.fit_k_core(ret, dist, cap=10.0, vol_target=0.06)
    assert out["events"] == 4 and out["active_sessions"] == 12
    assert out["k"] * out["sigma_active_annual"] == pytest.approx(0.06)
    assert out["cap_binding_rows"] == 0
    tight = x.fit_k_core(ret, dist, cap=1e-6, vol_target=0.06)
    assert tight["cap_binding_share"] == 1.0


def test_fit_k_core_refuses_a_test_row():
    ret, dist = _fit_panel()
    ret.index = pd.bdate_range("2022-06-01", periods=len(ret))
    with pytest.raises(x.Stage0Error):
        x.fit_k_core(ret, dist, cap=1.8, vol_target=0.06)


def test_declared_basket_excludes_unfound_declarations_and_keeps_late_ones():
    s = _sessions("2025-01-02", 40)
    p = 10
    ev = pd.DataFrame({"ticker": ["PTY"], "ex_date": [s[p]], "p": [p]})
    decl = pd.DataFrame({"status": 200, "ticker": ["PTY", "NAD", "HYT", "PDI"],
                         "ex_date": [s[p], s[p + 4], s[p + 5], s[p + 6]],
                         "declaration_date": [s[p - 5], pd.NaT, s[p + 1], s[p - 3]]})
    ok = pd.DataFrame(True, index=s, columns=list(x.NAMES))
    none = pd.DataFrame(columns=["ticker", "ex_date", "stock_split"])
    n_ex, c_ex = x.declared_baskets(ev, decl, s, ok, none, unknown="exclude")
    n_kp, c_kp = x.declared_baskets(ev, decl, s, ok, none, unknown="keep")
    # PDI out (declared by e-1); HYT in (declared after e-1: a surprise); NAD out only under "exclude"
    assert n_ex.iloc[0] == 16 - 2 and n_kp.iloc[0] == 16 - 1
    assert c_ex["no_release_legs"] == 1 and c_ex["declared_after_e_minus_1_legs_kept"] == 1


def test_x4_basis_check_passes_equal_closes_and_flags_a_basis_gap(tmp_path, monkeypatch):
    s = _sessions("2026-02-02", 15)
    cells = pd.DataFrame({"ticker": ["PTY", "PDI"], "date": [s[5], s[5]], "close": [10.0, 20.0], "volume": [1.0, 1.0]})
    adj = pd.DataFrame({"ticker": ["PTY", "PTY", "PDI", "PDI"], "date": [s[4], s[6], s[4], s[6]],
                        "close": [10.00, 10.10, 20.00, 20.60], "volume": 1.0})
    px = pd.DataFrame({"date": [s[4], s[6], s[4], s[6]], "ticker": ["PTY", "PTY", "PDI", "PDI"],
                       "close": [10.00, 10.10, 20.00, 20.00]})
    for name, df in (("bars.parquet", cells), ("adj.parquet", adj), ("px.parquet", px)):
        df.to_parquet(tmp_path / name, index=False)
    monkeypatch.setattr(x, "ALPACA_BARS", tmp_path / "bars.parquet")
    monkeypatch.setattr(x, "ALPACA_ADJ_BARS", tmp_path / "adj.parquet")
    monkeypatch.setattr(x, "PRICES", tmp_path / "px.parquet")
    rows, st = x.x4_basis_check(pd.DatetimeIndex(s))
    assert st["pass"] == 1 and st["fail"] == 1
    assert [r["ticker"] for r in rows] == ["PDI"] and rows[0]["check"] == "X4_basis_mismatch"
