"""E1's trial script (scripts/events/e1_merger_pair.py) on synthetic inputs.

Every claim is about the code, never the market (CLAUDE.md): synthetic prices with a
closed-form answer, synthetic EDGAR episodes, a fake EDGAR client. Nothing here reads
CRSP, R2, EDGAR or Alpaca; the root conftest blocks the network.

What is pinned:
* alignment (H1/H7): the decision row is the session before the fill, the fill is the
  target's first session after A, and the last decision row is two sessions before the
  exit; a leg that would fill on A raises (band_frontier.event_hold);
* a synthetic completed deal with a known answer: the buy-and-hold pair through
  `merger_pairs._announcement_row` and the constant-weight sleeve through `evaluate()` each
  equal their closed form, and the delisting return is booked on the payment date;
* the §6.3 guard: the target's post-delisting sessions spanned by its delisting return pass,
  a gap longer than ten sessions and a missing last return fail; nothing is filled;
* the kill rules at their boundaries, f_max's arithmetic, the stage order in `fit_core`;
* the gates: the fit reader never pulls, the holdout reader refuses an uncommitted fit
  verdict, the census keeps only unexplained episodes, a reading's quote must be re-found,
  and `stage_crsp` refuses sources that disagree;
* found 2026-10-22, before the fit ran, each checked to fail against the old code: one missing
  party fails DG-E1-1 while the other gates are still evaluated; the fit trades the ruled
  failed deals Stage 0 cleared, not the round-1 file; control 2 is keyed by deal, not permno.

The lookahead test (test_deal_window_alignment) was checked to fail against a deal_window
that set the decision row to the fill session itself (shift(1)), 2026-10-19.
"""
import json

import numpy as np
import pandas as pd
import pytest

from scripts.cef import band_frontier as bf
from scripts.events import crsp_events as ce
from scripts.events import e1_merger_pair as e1


# --------------------------------------------------------------------------- a synthetic world

def _px(dates, ret, prc=10.0):
    return pd.DataFrame({"prc": prc, "ret": ret, "retx": ret, "vol": 1000.0, "cfacpr": 1.0, "shrout": 1.0},
                        index=pd.DatetimeIndex(dates, name="date"))


def _world(r_t=0.001, r_a=0.0, dlret=0.002, dlpdt="2021-06-17"):
    """Target 1 and acquirer 9 trade every business day of 2021; A = Friday 2021-03-05; the
    target's last session is 2021-06-15 and the payment date 2021-06-17 (two sessions later)."""
    cal = pd.bdate_range("2021-01-04", "2021-12-31")
    t_dates = cal[cal <= "2021-06-15"]
    px = {1: _px(t_dates, r_t), 9: _px(cal, r_a)}
    e = pd.Series({"permno": 1, "nwperm": 9, "ticker": "TGT", "a_ticker": "ACQ", "comnam": "NUVEEN X MUN FD",
                   "seg": "muni", "dlstcd": 231, "dlstdt": pd.Timestamp("2021-06-15"),
                   "dlpdt": pd.Timestamp(dlpdt), "dlret": dlret, "dlamt": 10.0 * (1 + dlret),
                   "ann": pd.Timestamp("2021-03-05"), "failed": False, "fail_date": pd.NaT,
                   "group": "9@2021-03-05"})
    return cal, px, e


def test_deal_window_alignment():
    cal, px, e = _world()
    w = e1.deal_window(e, px, cal)
    assert w["d_in"] == pd.Timestamp("2021-03-08")          # Monday: the target's first session after A
    assert w["first"] == pd.Timestamp("2021-03-05")         # decided the evening of A, the session before the fill
    assert cal[cal.get_loc(w["first"]) + 1] == w["d_in"]
    assert w["exit"] == pd.Timestamp("2021-06-17")
    assert w["last"] == cal[cal.get_loc(w["exit"]) - 2]     # the last return earned is the exit's
    legs, _ = e1.legs_and_conversions(pd.DataFrame([{**e.to_dict(), **w}]))
    bf.event_hold(legs, cal)                                # no lookahead: does not raise
    with pytest.raises(AssertionError, match="lookahead"):
        bf.event_hold(legs.assign(ann=pd.Timestamp("2021-03-08")), cal)


def test_known_answer_completed_deal():
    r_t, r_a, dlret = 0.001, -0.0005, 0.002
    cal, px, e = _world(r_t, r_a, dlret)
    w = e1.deal_window(e, px, cal)
    n_t = int(((cal > w["d_in"]) & (cal <= e["dlstdt"])).sum())     # target sessions earned
    n_a = int(((cal > w["d_in"]) & (cal <= e["dlpdt"])).sum())      # acquirer sessions earned
    # buy and hold (the published `_announcement_row`), closed form
    rec = e1.price_completed(e, px)
    want = (1 + r_t) ** n_t * (1 + dlret) - 1 - ((1 + r_a) ** n_a - 1)
    assert rec["pair_A1_to_close"] == pytest.approx(want, abs=1e-14)
    # constant weight through event_hold + evaluate(): sum of daily w x (r_T - r_A), the
    # delisting return booked on the payment date, nothing earned on the NaN sessions between
    one = pd.DataFrame([{**e.to_dict(), **w}])
    R = e1.returns_matrix(px, cal, one)
    assert R.at[pd.Timestamp("2021-06-17"), 1] == pytest.approx(dlret)
    assert np.isnan(R.at[pd.Timestamp("2021-06-16"), 1])
    legs, _ = e1.legs_and_conversions(one)
    pnl = bf.evaluate(bf.event_hold(legs, cal), R.reindex(columns=[1, 9]))["pnl"]
    assert pnl.sum() == pytest.approx(n_t * r_t + dlret - n_a * r_a, abs=1e-14)
    assert pnl.loc[:w["d_in"]].abs().sum() == 0.0                    # nothing earned on or before the fill


def test_hold_gaps_guard():
    # payment 15 sessions after the last trade: only the delisting-return span admits the gap
    cal, px, e = _world(dlpdt="2021-07-07")
    w = e1.deal_window(e, px, cal)
    R = e1.returns_matrix(px, cal, pd.DataFrame([{**e.to_dict(), **w}]))
    span = (e["dlstdt"], e["dlpdt"])
    assert e1.hold_gaps(R[1], w["d_in"], w["exit"], span) is None            # spanned by the delisting return
    assert "gap of" in e1.hold_gaps(R[1], w["d_in"], w["exit"])               # without the span: a 15-session gap
    r = R[9].copy()
    r.loc["2021-04-01":"2021-04-16"] = np.nan                                 # 12 sessions
    assert "gap of 12" in e1.hold_gaps(r, w["d_in"], w["exit"])
    r = R[9].copy()
    r.loc["2021-04-01":"2021-04-08"] = np.nan                                 # 6 sessions, spanned by the next return
    assert e1.hold_gaps(r, w["d_in"], w["exit"]) is None
    r = R[9].copy()
    r.loc[w["exit"]] = np.nan
    assert "last earned session" in e1.hold_gaps(r, w["d_in"], w["exit"])


def test_failed_deal_exits_at_the_close_after_the_failure_filing():
    cal, px, e = _world()
    e = e.copy()
    e["failed"] = True
    F = pd.Timestamp("2021-05-07")                                  # a Friday
    rec = e1.price_failed(e, px, cal, F)
    assert rec["exit"] == pd.Timestamp("2021-05-10")
    n = int(((cal > rec["d_in"]) & (cal <= rec["exit"])).sum())
    assert rec["pair"] == pytest.approx((1.001) ** n - 1, abs=1e-14)


def test_control1_window_is_a_year_earlier_and_as_long():
    cal = pd.bdate_range("2019-01-01", "2021-12-31")
    px = {1: _px(cal, 0.001), 9: _px(cal, 0.0)}
    e = pd.Series({"permno": 1, "nwperm": 9})
    d_in, end_t = pd.Timestamp("2021-06-01"), pd.Timestamp("2021-08-31")
    c = e1.control1(e, px, d_in, end_t)
    td = px[1].index
    assert c["c1"] == td[td.get_loc(d_in) - e1.CTRL_LAG]
    assert c["L"] == int(((td > d_in) & (td <= end_t)).sum())
    assert c["ctrl"] == pytest.approx(1.001 ** c["L"] - 1, abs=1e-14)
    short = {1: _px(cal[cal >= "2021-01-04"], 0.001), 9: px[9]}
    assert np.isnan(e1.control1(e, short, d_in, end_t)["ctrl"])     # precedes the listing: no control, counted


@pytest.mark.parametrize("med, t, ok", [(0.0061, 2.0, True), (0.0060, 5.0, False), (0.01, 1.99, False)])
def test_stage1_boundaries(med, t, ok):
    assert e1.stage1_passes(med, t) is ok


@pytest.mark.parametrize("ctrl, treat, kills", [(0.005, 0.01, True), (0.0049, 0.01, False), (-0.02, 0.01, False),
                                                 (np.nan, 0.01, True)])
def test_control_kill_rule(ctrl, treat, kills):
    assert e1.control_kills(ctrl, treat) is kills


def test_f_max_arithmetic():
    # PREREG §5.3's own scale arithmetic: m = 167.4bp, D = 243.5 days -> f_be ~ 1.99%/yr, f_max ~ 1.0%/yr
    f = e1.f_max(0.01674, 243.5)
    assert f["f_be_pct"] == pytest.approx((0.01674 - 0.003) * 360 / (1.02 * 243.5) * 100)
    assert round(f["f_be_pct"], 2) == 1.99 and f["f_max_pct"] == pytest.approx(f["f_be_pct"] / 2)


def _synthetic_P(n_groups=12, per=2, seed=7):
    """Priced deals over 2015-2020 on a synthetic calendar, with returns R whose pair P&L is
    positive by construction (the target drifts up 4bp a day against the acquirer)."""
    rng = np.random.default_rng(seed)
    cal = pd.bdate_range("2014-12-01", "2021-03-31")
    rows, cols = [], {}
    for g in range(n_groups):
        a = cal[60 + g * 100]
        acq = 900 + g
        cols[acq] = rng.normal(0, 0.006, len(cal))
        for j in range(per):
            t = 100 + g * 10 + j
            cols[t] = cols[acq] + 0.0004 + rng.normal(0, 0.004, len(cal))
            i_in = cal.get_loc(a) + 1
            ex = cal[i_in + 120]
            rows.append({"permno": t, "nwperm": acq, "ticker": f"T{t}", "seg": "muni", "group": f"{acq}@{a.date()}",
                         "ann": a, "failed": j == 1 and g % 3 == 0, "d_in": cal[i_in], "exit": ex,
                         "first": cal[i_in - 1], "last": cal[cal.get_loc(ex) - 2], "dlstdt": ex, "dlpdt": ex,
                         "days": int((ex - cal[i_in]).days)})
    R = pd.DataFrame(cols, index=cal)
    P = pd.DataFrame(rows)
    P["pair"] = [float((R.loc[r.d_in:r.exit, r.permno].iloc[1:] - R.loc[r.d_in:r.exit, r.nwperm].iloc[1:]).sum())
                 for r in P.itertuples()]
    P["units"] = np.where(P["failed"], 4.0, 2.0 + P["pair"].abs())
    X = pd.DataFrame(rng.normal(0, 0.01, (len(cal), len(e1.FF6) + 3)), index=cal,
                     columns=list(e1.FF6) + list(e1.ETF_TICKERS))
    return P, R, cal, X


def test_fit_core_stage_order_and_sizing():
    P, R, cal, X = _synthetic_P()
    # controls: control 1 at 60% of each deal's pair (stage 2 must kill), control 2 tiny
    P["ctrl1"], P["ctrl2"] = 0.6 * P["pair"], 0.0
    res = e1.fit_core(P, R, cal, X, vol_target=0.10, cap=None)
    assert res["deals"] == len(P) and res["failed"] == int(P["failed"].sum())
    assert res["stage1"]["median"] == pytest.approx(P["pair"].median())
    assert res["stage2"]["kills"] and res["verdict"].startswith("KILL (stage 2")
    # every later stage is still computed
    for k in ("stage3", "stage4", "stage5", "stage6"):
        assert k in res
    S = res["sleeve"]
    assert S["k"] * S["sigma_raw"] == pytest.approx(0.10)                     # k = vol_target / sigma_fit
    assert S["pnl"].std() * np.sqrt(252) == pytest.approx(0.10, rel=1e-9)      # no cap: sized to the target
    assert res["stage6"]["N"] == e1.N_EVENTS
    # with harmless controls the first failing rule moves on
    P["ctrl1"] = -0.1 * P["pair"]
    res2 = e1.fit_core(P, R, cal, X, vol_target=0.10, cap=None)
    assert not res2["stage2"]["kills"] and not res2["verdict"].startswith("KILL (stage 2")
    P["ctrl2"] = np.nan                                                        # no control 2 anywhere
    assert e1.fit_core(P, R, cal, X, vol_target=0.10, cap=None)["verdict"].startswith("HALT (stage 3")


def test_conversion_turnover_is_the_residual_in_the_sleeve():
    P, R, cal, X = _synthetic_P(n_groups=1, per=1)
    P["failed"] = False
    S = e1.sleeve(P, R, cal, k=1.0, cap=None, vol_target=np.nan)
    c = S["conversions"].iloc[0]
    assert c["residual"] == pytest.approx(abs(R.at[P["exit"].iloc[0], P["permno"].iloc[0]]
                                              - R.at[P["exit"].iloc[0], P["nwperm"].iloc[0]]))
    assert S["turn"].sum() == pytest.approx(2.0 + c["residual"])               # entry legs + residual only


# --------------------------------------------------------------------------- gates

def test_fit_reader_never_pulls(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "CACHE", tmp_path)
    with pytest.raises(e1.GateError, match="stage-crsp"):
        e1.fit_daily([1, 2, 3])
    with pytest.raises(e1.GateError, match="crsp_events.py"):
        e1.crsp_tables()


def test_holdout_reader_refuses_an_uncommitted_fit_verdict(tmp_path):
    f = e1.REPO / "results" / "events" / "e1" / "_cache_e1" / "not_a_fit_verdict.json"  # gitignored, never committed
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"stage7_fit_verdict_written": True, "verdict": "FIT PASSES STAGES 1-6"}))
    try:
        with pytest.raises(e1.GateError, match="not committed"):
            e1.holdout_gate(f)
    finally:
        f.unlink()


def test_failed_census_keeps_only_unexplained_episodes():
    ep = pd.DataFrame({"cik": [10, 20, 30], "first_date": pd.to_datetime(["2015-01-05", "2015-01-05", "2024-03-01"]),
                       "last_date": pd.to_datetime(["2015-06-01", "2015-06-01", "2024-05-01"]),
                       "first_form": ["425", "N-14 8C", "425"], "first_accession": ["a-1", "b-2", "c-3"],
                       "n_filings": [3, 2, 1], "forms": ["425", "N-14 8C", "425"], "company_last": ["X", "Y", "Z"]})
    comp = pd.DataFrame({"cik": [10.0, 20.0, np.nan], "C": pd.to_datetime(["2015-09-01", "2018-01-01", "2015-02-01"])})
    c = e1.failed_census(ep, comp)
    assert list(c["episode_cik"]) == [20, 30]          # 10 completed within 730 days; 20's completion is too late
    assert list(c["window_past_crsp"]) == [False, True]


class _FakeClient:
    def __init__(self, text):
        self.text = text

    def get_text(self, url):
        return self.text


def test_readings_must_cover_every_candidate_and_quotes_must_be_found(tmp_path, monkeypatch):
    cen = pd.DataFrame({"episode_cik": [20], "episode_accession": ["0000000020-15-000001"]})
    monkeypatch.setattr(e1, "READINGS", tmp_path / "r.csv")
    _, probs = e1.check_readings(cen, _FakeClient(""))
    assert probs and "does not exist" in probs[0]
    row = {c: "" for c in e1.READING_COLUMNS}
    row.update(episode_cik="20", episode_accession="0000000020-15-000001", outcome="terminated", in_trial="Y",
               deal_id="20>30", both_listed="Y", acquirer_cik="30",
               target_cik="20", target_ticker="TGT", acquirer_ticker="ACQ", ann_date="2015-01-05",
               ann_accession="0000000020-15-000001", ann_quote="the Boards approved the reorganization",
               fail_date="2015-06-01", fail_accession="0000000020-15-000009", fail_quote="the reorganization was terminated")
    pd.DataFrame([row]).to_csv(tmp_path / "r.csv", index=False)
    _, probs = e1.check_readings(cen, _FakeClient("The Boards approved the reorganization. Later the "
                                                  "reorganization was terminated."))
    assert probs == []
    _, probs = e1.check_readings(cen, _FakeClient("nothing relevant"))
    assert any("quote not found" in p for p in probs)
    _, probs = e1.check_readings(pd.concat([cen, cen.assign(episode_accession="x")]), _FakeClient(""))
    assert any("no reading" in p for p in probs)
    # the acquirer's episode reads the same deal with another outcome: a disagreement fails the gate
    two = pd.DataFrame([row, {**row, "episode_cik": "30", "episode_accession": "0000000030-15-000002",
                              "outcome": "completed", "in_trial": "N"}])
    two.to_csv(tmp_path / "r.csv", index=False)
    cen2 = pd.concat([cen, pd.DataFrame({"episode_cik": [30], "episode_accession": ["0000000030-15-000002"]})])
    _, probs = e1.check_readings(cen2, _FakeClient("The Boards approved the reorganization. Later the "
                                                   "reorganization was terminated."))
    assert any("disagree" in p for p in probs)
    # a blank outcome blocks
    pd.DataFrame([{**row, "outcome": "", "in_trial": "N"}]).to_csv(tmp_path / "r.csv", index=False)
    _, probs = e1.check_readings(cen, _FakeClient("The Boards approved the reorganization."))
    assert any("blank outcome" in p for p in probs)


def _src(tmp_path, name, df):
    d = tmp_path / name
    d.mkdir()
    df.to_parquet(d / "dsf_abc.parquet")
    (d / "_manifest.json").write_text(json.dumps({"dsf_abc": {
        "pulled_utc": "2026-10-12T00:00:00+00:00", "sql": "... AND date < DATE '2023-01-01'"}}))
    return d


def test_stage_crsp_assembles_and_refuses_disagreement(tmp_path, monkeypatch):
    monkeypatch.setattr(ce, "CACHE", tmp_path / "cache")
    rows = pd.DataFrame({"permno": [1, 1, 2], "date": pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-02"]),
                         "prc": [10.0, -10.1, 5.0], "ret": [np.nan, 0.01, 0.0], "retx": [np.nan, 0.01, 0.0],
                         "vol": [1.0, 1.0, 1.0], "shrout": [1.0, 1.0, 1.0], "cfacpr": [1.0, 1.0, 1.0]})
    a, b = _src(tmp_path, "a", rows.iloc[:2]), _src(tmp_path, "b", rows.iloc[1:])
    out, missing = e1.stage_crsp([1, 2], [a, b])
    assert missing == [] and len(pd.read_parquet(out)) == 3
    assert e1.fit_daily([1, 2])["prc"].min() > 0                    # the reader returns |prc|
    c = _src(tmp_path, "c", rows.iloc[1:2].assign(ret=0.02))
    with pytest.raises(e1.GateError, match="disagree"):
        e1.stage_crsp([1], [a, c])
    d = _src(tmp_path, "d", rows.iloc[1:2].assign(ret=np.nan))
    with pytest.raises(e1.GateError, match="disagree"):
        e1.stage_crsp([1], [a, d])                                   # a return missing in one source only
    with pytest.raises(e1.GateError, match="no source extract"):
        e1.stage_crsp([1, 3], [a])
    out, missing = e1.stage_crsp([1, 3], [a], partial=True)
    assert missing == [3]


def test_group_bootstrap_is_reproducible_and_clustered():
    v = pd.Series([0.01, 0.012, -0.004, 0.02, 0.0, 0.015])
    g = pd.Series(["a", "a", "b", "c", "c", "d"])
    one, two = e1.group_boot(v, g, reps=500), e1.group_boot(v, g, reps=500)
    assert one == two
    assert one["mean_lo"] <= v.mean() <= one["mean_hi"]


@pytest.mark.parametrize("verdict, opens", [
    ("FIT PASSES STAGES 1-6", True), ("KILL D4 (stage 5)", True), ("NEITHER (stage 6: below the bar at N = 6)", True),
    ("KILL D1 (stage 1)", True), ("HALT (stage 3: fewer than 75% of deals have a control 2)", False)])
def test_holdout_opens_per_reading_r12(verdict, opens):
    """R12, ruled 2026-10-20: every committed verdict but a HALT opens the holdout (report-only
    after a KILL or NEITHER). Checked to fail on the KILL/NEITHER cases with the pre-ruling None."""
    assert e1.holdout_opens(verdict) is opens


# --------------------------------------------------------------------------- found 2026-10-22, before the fit

def _reader_missing(missing: int, rows: pd.DataFrame):
    """A fit reader that refuses, as `fit_daily` does, any set holding a permno with no cached rows."""
    def read(perms):
        if missing in set(perms):
            raise e1.GateError(f"DG-E1-1: no cached CRSP extract for these {len(perms)} permnos")
        return rows[rows["permno"].isin(perms)]
    return read


def test_stage0_one_missing_party_fails_dg1_and_still_checks_the_other_gates():
    """2026-10-22: ALD (a failed fit deal's party) had no CRSP rows. DG-E1-1 must FAIL on the full
    set, and a fallback read must never pass it; DG-E1-4's completed deals, -5 and -7 are still
    evaluated on the completed deals' extract, and DG-E1-4 stays INCOMPLETE, naming the failed
    deal it could not check. Checked to fail against the behaviour before b5e2130 (no fallback
    read: one missing party left no extract, so DG-E1-4/5/7 all failed with DG-E1-1's cause)."""
    rows = pd.DataFrame({"permno": [1, 9], "date": pd.to_datetime(["2021-01-04", "2021-01-04"]), "prc": 10.0})
    read = _reader_missing(5, rows)
    d, loaded, text = e1.fit_extract({1, 9, 5}, {1, 9}, reader=read)
    assert text.startswith("FAIL") and "evaluated on the completed fit deals' extract" in text
    assert d is not None and loaded == {1, 9} and set(d["permno"]) == {1, 9}
    assert e1.dg1_status(text, "PASS (refuses)", [], [], True) == "FAIL"
    ff = pd.DataFrame([{"ticker": "ALD", "a_ticker": "PSEC", "permno": 5, "nwperm": 9},
                       {"ticker": "RAA", "a_ticker": "BFZ", "permno": 1, "nwperm": 9}])
    px = {1: _px(["2021-01-04"], 0.0), 9: _px(["2021-01-04"], 0.0)}
    unchecked = e1.unpriced_failed(ff, px)
    assert unchecked == ["ALD -> PSEC"]
    g = e1.dg4_gate({}, {}, unchecked)
    assert g["status"] == "INCOMPLETE" and "ALD -> PSEC" in g["detail"]
    # failed deals not yet known (DG-E1-3 open): nothing is read in the full set's place
    d, loaded, text = e1.fit_extract({1, 9, 5}, None, reader=read)
    assert d is None and text.startswith("FAIL")
    # every party present: DG-E1-1 and DG-E1-4 pass
    d, loaded, text = e1.fit_extract({1, 9}, {1, 9}, reader=read)
    assert text.startswith("PASS") and loaded == {1, 9}
    assert e1.dg1_status(text, "PASS (refuses)", [], [], True) == "PASS"
    assert e1.dg1_status(text, "PASS (refuses)", [], [], False) == "INCOMPLETE"
    assert e1.dg1_status(text, "PASS (refuses)", [123], [], True) == "FAIL"    # a control-2 fund lacks rows
    assert e1.dg4_gate({}, {}, [])["status"] == "PASS"


def test_fit_trades_the_ruled_failed_deals_stage0_cleared(tmp_path, monkeypatch):
    """The fit and the holdout read the RULED readings Stage 0 wrote, checked against the
    Stage-0 record; before 2026-10-22 `_load_trial_deals` read the round-1 file (3 in-trial
    deals of the 13 Stage 0 cleared). Checked to fail against that code."""
    cols = {"target_ticker": "ticker", "acquirer_ticker": "a_ticker"}
    pd.DataFrame({"target_ticker": ["OLD"], "acquirer_ticker": ["ONE"]}).to_csv(tmp_path / "r1.csv", index=False)
    ruled = tmp_path / "ruled.csv"
    pd.DataFrame({"target_ticker": ["AAA", "CCC"], "acquirer_ticker": ["BBB", "DDD"]}).to_csv(ruled, index=False)
    rec = tmp_path / "stage0.json"
    rec.write_text(json.dumps({"gates": {"DG-E1-3": {"in_trial_deal_list": ["AAA->BBB", "CCC->DDD"]}}}))
    hd = tmp_path / "hd.csv"
    pd.DataFrame({"permno": []}).to_csv(hd, index=False)
    monkeypatch.setattr(e1, "READINGS", tmp_path / "r1.csv")
    monkeypatch.setattr(e1, "READINGS_RULED", ruled)
    monkeypatch.setattr(e1, "STAGE0_JSON", rec)
    monkeypatch.setattr(e1, "HOLDOUT_DATES", hd)
    monkeypatch.setattr(e1, "failed_deal_rows", lambda r, nm: r.rename(columns=cols).assign(part="fit_seen"))
    monkeypatch.setattr(e1, "deal_table", lambda nm, dl: pd.DataFrame({"permno": [1]}))
    monkeypatch.setattr(e1, "load_fit_dates", lambda x: pd.DataFrame({"permno": [1]}))
    monkeypatch.setattr(e1, "attach_dates", lambda x, d: x)
    _, fail = e1._load_trial_deals(None, None, None)
    assert sorted(fail["ticker"] + "->" + fail["a_ticker"]) == ["AAA->BBB", "CCC->DDD"]
    rec.write_text(json.dumps({"gates": {"DG-E1-3": {"in_trial_deal_list": ["AAA->BBB"]}}}))
    with pytest.raises(e1.GateError, match="only here"):
        e1._load_trial_deals(None, None, None)
    rec.write_text(json.dumps({"gates": {"DG-E1-3": {}}}))
    with pytest.raises(e1.GateError, match="no in-trial deal list"):
        e1._load_trial_deals(None, None, None)
    ruled.unlink()
    with pytest.raises(e1.GateError, match="run stage0"):
        e1._load_trial_deals(None, None, None)


def test_control2_is_keyed_by_the_deal_not_the_target_permno():
    """NCU is the target of two fit deals (failed 2011, completed 2013-14). Control 2 is attached
    by the deal's row in the deal table; a permno key gave both deals one value. `price_deals`
    carries that row and the deal's set. Checked to fail against the permno key."""
    P = pd.DataFrame({"row": [3, 8, 9], "permno": [7, 7, 4], "pair": [0.01, 0.02, 0.0]})
    out = e1.attach_ctrl2(P, {3: 0.005, 8: -0.001})
    assert out["ctrl2"].iloc[0] == 0.005 and out["ctrl2"].iloc[1] == -0.001 and np.isnan(out["ctrl2"].iloc[2])
    with pytest.raises(ValueError, match="one `row` per deal"):
        e1.attach_ctrl2(P.assign(row=[3, 3, 9]), {})
    cal, px, e = _world()
    D = pd.DataFrame([{**e.to_dict(), "part": "fit_seen"}], index=[5])
    Pd, excl = e1.price_deals(D, px, cal, e1.returns_matrix(px, cal, D))
    assert excl == {} and Pd["row"].tolist() == [5] and Pd["part"].tolist() == ["fit_seen"]
