"""`quantt/session/dist_score.py`: the distribution-adjusted third score.

What these pin (team lead 2026-10-09, `docs/SYSTEM.md` §5; the module docstring;
the review of 2026-10-09):
  * entitlement: shares held at the START of the ex-date, as verify recorded them
    (`held_into_close`), are credited if long and charged if short. D's fills,
    and the end-of-day positions, are not what is entitled;
  * the two-source rule: Alpaca primary, the yfinance panel a cross-check within
    rounding; a real conflict, or panel-only, is UNMEASURED naming both; never
    averaged;
  * a zero needs BOTH sources silent with the panel current, i.e. rewritten after
    the close of the session following D, AND holding rows for the name. Alpaca's
    silence alone is UNMEASURED (review 2026-10-11: an uncovered name was a zero);
  * the lag: D is scored only once two sessions have closed after it;
  * records: one row per D; an UNMEASURED row is replaced by a later measurement,
    a measured row never is; a failure is a row naming it;
  * inside verify: never the verdict, never the exit code.
Hermetic: a fake client, a temporary state dir, a temporary panel file.
"""
import ast
import csv
import datetime as dt
import inspect
import json
import os

import pandas as pd
import pytest

from ops.schedule.nyse_calendar import next_trading_day, previous_trading_day
from quantt.session import dist_score as ds
from quantt.session import verify as vf

D = dt.date(2026, 10, 14)          # Wednesday: the ex-date under test
NEXT = dt.date(2026, 10, 15)       # the session after D
TODAY = dt.date(2026, 10, 16)      # two sessions after D: D is due
NOW = dt.datetime(2026, 10, 16, 21, 30, tzinfo=dt.timezone.utc)
ET = ds.ET
CAL = dict(previous_trading_day=previous_trading_day, next_trading_day=next_trading_day)


def ev(sym, amount, ex=D, kind="cash_dividend", i=None):
    return {"id": i or f"{sym}-{ex}-{amount}", "symbol": sym, "ex_date": ex, "amount": amount,
            "kind": kind, "special": False, "sub_type": None}


def panel(rows):
    return pd.DataFrame(rows, columns=["ticker", "ex_date", "amount"]).assign(
        ex_date=lambda d: pd.to_datetime(d["ex_date"]))


def write_panel(tmp_path, rows, *, written_et):
    p = tmp_path / "panel.parquet"
    panel(rows).to_parquet(p)
    ts = written_et.timestamp()
    os.utime(p, (ts, ts))
    return p


AFTER_NEXT_CLOSE = dt.datetime.combine(NEXT, dt.time(18, 0), ET)    # current for D
BEFORE_NEXT_CLOSE = dt.datetime.combine(NEXT, dt.time(15, 0), ET)   # not yet current


class FakeClient:
    def __init__(self, events=(), exc=None):
        self.events, self.exc, self.calls = list(events), exc, []

    def distributions(self, symbols, start, end):
        self.calls.append((tuple(symbols), start, end))
        if self.exc:
            raise self.exc
        return list(self.events)


def session(state, day=D, *, held=None, auction="50.00", positions_after=None, extra_rows=()):
    """What verify leaves behind for `day`: reconcile.json and a scores.csv row."""
    d = state / day.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    rec = {"verdict": "x", "held_into_close": held if held is not None else {"PDI": 100},
           "positions_after": positions_after or {}}
    (d / "reconcile.json").write_text(json.dumps(rec))
    p = state / "scores.csv"
    new = not p.exists()
    with p.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=vf.SCORES_COLUMNS)
        if new:
            w.writeheader()
        for a in (auction, *extra_rows):
            w.writerow({**{c: "" for c in vf.SCORES_COLUMNS}, "date": day.isoformat(),
                        "auction_pnl_usd": a})


def rows_of(state):
    p = state / "distribution_scores.csv"
    with p.open(newline="") as fh:
        return list(csv.DictReader(fh))


def run(state, client, panel_path, today=TODAY):
    return ds.run_pending(client, state, today, now_utc=NOW, panel_path=panel_path, **CAL)


# ------------------------------------------------------------------ the rule

def test_a_long_is_credited_and_a_short_is_charged():
    pnl, rows, un = ds.score({"PDI": 100, "PTY": -200}, {"PDI": 0.2205, "PTY": 0.1188}, {})
    assert un == [] and pnl == pytest.approx(100 * 0.2205 - 200 * 0.1188)
    by = {r["symbol"]: r for r in rows}
    assert by["PDI"]["dist_pnl"] > 0 and by["PTY"]["dist_pnl"] < 0


def test_a_missing_term_makes_the_sum_unmeasured():
    pnl, _, un = ds.score({"PDI": 100, "PTY": 50}, {"PDI": 0.22}, {"PTY": "sources disagree"})
    assert pnl is None and un == ["PTY: sources disagree"]


@pytest.mark.parametrize("per_share,gaps", [({}, {}), ({"PDI": 0.1}, {"PDI": "x"})])
def test_a_symbol_must_be_resolved_exactly_once(per_share, gaps):
    with pytest.raises(ds.DistError, match="exactly one"):
        ds.score({"PDI": 100}, per_share, gaps)


@pytest.mark.parametrize("q", [0, 1.5, True])
def test_held_must_be_non_zero_whole_shares(q):
    with pytest.raises(ds.DistError, match="non-zero int"):
        ds.score({"PDI": q}, {"PDI": 0.1}, {})


@pytest.mark.parametrize("a", [-0.01, float("nan"), float("inf"), "0.1", None])
def test_a_per_share_amount_must_be_a_finite_non_negative_number(a):
    with pytest.raises(ds.DistError, match="per-share"):
        ds.score({"PDI": 100}, {"PDI": a}, {})


def test_entitlement_is_the_book_held_into_d_not_the_end_of_day_positions(tmp_path):
    """D's fills (here: PDI covered and PTY bought on D) earn nothing: positions_after
    differs from held_into_close, and only the latter is scored."""
    session(tmp_path, held={"PDI": -100}, positions_after={"PTY": 300})
    p = write_panel(tmp_path, [("PDI", D, 0.221), ("PTY", D, 0.119)], written_et=AFTER_NEXT_CLOSE)
    run(tmp_path, FakeClient([ev("PDI", 0.2205), ev("PTY", 0.1188)]), p)
    r, = rows_of(tmp_path)
    assert r["distribution_pnl_usd"] == f"{-100 * 0.2205:.2f}"
    assert [x["symbol"] for x in json.loads(r["per_symbol_json"])] == ["PDI"]


# ------------------------------------------------------- the two-source rule

def _resolve(alp, pan, current=True):
    return ds.resolve(["S"], D, alp, panel(pan), panel_current=current, panel_note="n")


def test_agreement_within_rounding_uses_alpacas_more_precise_amount():
    ps, gaps, notes, events = _resolve([ev("S", 0.0595)], [("S", D, 0.060)])
    assert ps == {"S": 0.0595} and gaps == {} and "Alpaca used" in notes["S"]
    assert events["S"] == [{"id": "S-2026-10-14-0.0595", "kind": "cash_dividend", "amount": 0.0595}]


def test_a_real_conflict_is_unmeasured_naming_both_and_never_averaged():
    ps, gaps, _, _ = _resolve([ev("S", 0.2205)], [("S", D, 0.25)])
    assert ps == {} and "Alpaca 0.2205" in gaps["S"] and "0.25" in gaps["S"] and "not averaged" in gaps["S"]


def test_only_alpaca_listing_d_uses_alpaca():
    ps, gaps, notes, _ = _resolve([ev("S", 0.2205)], [])
    assert ps == {"S": 0.2205} and "does not list" in notes["S"]


def test_only_the_panel_listing_d_is_unmeasured_because_silence_is_not_zero():
    ps, gaps, _, _ = _resolve([], [("S", D, 0.221)])
    assert ps == {} and "silence is not a zero" in gaps["S"]


def test_neither_listing_d_is_zero_only_when_the_panel_is_current():
    covers_s = [("S", D - dt.timedelta(days=30), 0.22)]           # S's last payout, a month before D
    ps, gaps, notes, _ = _resolve([], covers_s, current=True)
    assert ps == {"S": 0.0} and "none listed" in notes["S"]
    ps, gaps, _, _ = _resolve([], covers_s, current=False)
    assert ps == {} and "not yet current" in gaps["S"]


def test_a_name_the_panel_does_not_cover_is_never_a_zero():
    """Review 2026-10-11: a current panel FILE with no rows for the name (an empty
    yfinance fetch, or a name outside the panel's universe) is one silent source."""
    ps, gaps, notes, _ = _resolve([], [("OTHER", D, 0.10)], current=True)
    assert ps == {} and "no rows for S" in gaps["S"] and "not a zero" in gaps["S"]


def test_two_events_on_one_ex_date_are_summed_and_both_recorded():
    alp = [ev("S", 0.2205, i="a"), ev("S", 0.5, i="b", kind="capital_gains_distribution")]
    ps, gaps, _, events = _resolve(alp, [("S", D, 0.221), ("S", D, 0.5)])
    assert ps["S"] == pytest.approx(0.7205) and gaps == {}
    assert {e["kind"] for e in events["S"]} == {"cash_dividend", "capital_gains_distribution"}


def test_the_panel_is_current_only_after_the_next_sessions_close():
    need = ds._session_close_utc(NEXT)
    assert ds.panel_judgement(D, need, D, NEXT)[0] is True
    assert ds.panel_judgement(D, need - dt.timedelta(seconds=1), D, NEXT)[0] is False
    assert ds.panel_judgement(D, None, None, NEXT) == (False, "panel absent")


# ------------------------------------------------------------- the run and its records

def test_d_is_scored_two_sessions_later_with_the_combined_line(tmp_path):
    session(tmp_path, held={"PDI": 100, "PTY": -200}, auction="50.00")
    p = write_panel(tmp_path, [("PDI", D, 0.221), ("PTY", D, 0.119)], written_et=AFTER_NEXT_CLOSE)
    c = FakeClient([ev("PDI", 0.2205), ev("PTY", 0.1188)])
    assert run(tmp_path, c, p) == [(D, f"{100 * 0.2205 - 200 * 0.1188:.2f}")]
    r, = rows_of(tmp_path)
    want = 100 * 0.2205 - 200 * 0.1188
    assert r["auction_pnl_with_distributions_usd"] == f"{50.0 + want:.2f}"
    assert not (tmp_path / "scores.csv").read_text().count("distribution")
    (syms, start, end), = c.calls
    assert syms == ("PDI", "PTY") and start == D - dt.timedelta(days=120) and end == D + dt.timedelta(days=120)


def test_a_session_younger_than_the_lag_is_not_scored_yet(tmp_path):
    session(tmp_path, day=NEXT)
    p = write_panel(tmp_path, [], written_et=AFTER_NEXT_CLOSE)
    assert run(tmp_path, FakeClient(), p) == []
    assert not (tmp_path / "distribution_scores.csv").exists()


def test_a_stale_panel_leaves_the_day_unmeasured_and_a_later_run_measures_it(tmp_path):
    session(tmp_path, held={"PDI": 100})
    pdi_earlier = [("PDI", D - dt.timedelta(days=30), 0.221)]
    stale = write_panel(tmp_path, pdi_earlier, written_et=BEFORE_NEXT_CLOSE)
    run(tmp_path, FakeClient([]), stale)
    r, = rows_of(tmp_path)
    assert r["distribution_pnl_usd"] == ds.UNMEASURED and "not yet current" in r["unmeasured"]
    fresh = write_panel(tmp_path, pdi_earlier, written_et=AFTER_NEXT_CLOSE)
    run(tmp_path, FakeClient([]), fresh)
    r, = rows_of(tmp_path)
    assert r["distribution_pnl_usd"] == "0.00"


def test_an_uncovered_held_name_leaves_the_day_open_until_alpaca_lists_it(tmp_path):
    """Review 2026-10-11, synthetic: FCT held long, absent from a current panel, and
    Alpaca not yet listing its ex-date. The old rule wrote a final −23.76 (PTY only);
    the day must stay UNMEASURED and take FCT's amount once Alpaca lists it."""
    session(tmp_path, held={"FCT": 500, "PTY": -200})
    p = write_panel(tmp_path, [("PTY", D, 0.119)], written_et=AFTER_NEXT_CLOSE)
    run(tmp_path, FakeClient([ev("PTY", 0.1188)]), p)
    r, = rows_of(tmp_path)
    assert r["distribution_pnl_usd"] == ds.UNMEASURED and "no rows for FCT" in r["unmeasured"]
    run(tmp_path, FakeClient([ev("PTY", 0.1188), ev("FCT", 0.07)]), p)
    r, = rows_of(tmp_path)
    assert r["distribution_pnl_usd"] == f"{500 * 0.07 - 200 * 0.1188:.2f}"


def test_an_error_row_is_replaced_by_a_later_measurement(tmp_path):
    session(tmp_path, held={"PDI": 100})
    p = write_panel(tmp_path, [("PDI", D, 0.221)], written_et=AFTER_NEXT_CLOSE)
    run(tmp_path, FakeClient(exc=RuntimeError("data API 503")), p)
    r, = rows_of(tmp_path)
    assert r["distribution_pnl_usd"] == ds.UNMEASURED and "503" in r["unmeasured"]
    run(tmp_path, FakeClient([ev("PDI", 0.2205)]), p)
    r, = rows_of(tmp_path)
    assert r["distribution_pnl_usd"] == "22.05"


def test_a_measured_row_is_final(tmp_path):
    session(tmp_path, held={"PDI": 100})
    p = write_panel(tmp_path, [("PDI", D, 0.221)], written_et=AFTER_NEXT_CLOSE)
    run(tmp_path, FakeClient([ev("PDI", 0.2205)]), p)
    c = FakeClient([ev("PDI", 9.99)])
    assert run(tmp_path, c, p) == [] and c.calls == []
    assert rows_of(tmp_path)[0]["distribution_pnl_usd"] == "22.05"
    with pytest.raises(ds.DistError, match="measured row"):
        ds.upsert(tmp_path / "distribution_scores.csv", {**rows_of(tmp_path)[0]})


def test_scores_rows_that_disagree_are_named_never_picked(tmp_path):
    session(tmp_path, auction="50.00", extra_rows=("51.00",))
    p = write_panel(tmp_path, [], written_et=AFTER_NEXT_CLOSE)
    run(tmp_path, FakeClient([]), p)
    r, = rows_of(tmp_path)
    assert r["distribution_pnl_usd"] == ds.UNMEASURED and "disagree" in r["unmeasured"]


@pytest.mark.parametrize("first,second", [("50.00", ds.UNMEASURED), (ds.UNMEASURED, "50.00")])
def test_an_unmeasured_scores_row_beside_a_measured_one_is_not_a_disagreement(tmp_path, first, second):
    """Review 2026-10-11: a same-evening verify re-run left one UNMEASURED and one
    measured auction row for D, which raised "disagree" and made the whole day an
    error row for good. The measured auction value stands, in either order."""
    session(tmp_path, held={"PDI": 100}, auction=first, extra_rows=(second,))
    p = write_panel(tmp_path, [("PDI", D, 0.221)], written_et=AFTER_NEXT_CLOSE)
    run(tmp_path, FakeClient([ev("PDI", 0.2205)]), p)
    r, = rows_of(tmp_path)
    assert (r["auction_pnl_usd"], r["distribution_pnl_usd"], r["auction_pnl_with_distributions_usd"]) \
        == ("50.00", "22.05", "72.05")


def test_an_unmeasured_auction_makes_only_the_combined_line_unmeasured(tmp_path):
    session(tmp_path, held={"PDI": 100}, auction=ds.UNMEASURED)
    p = write_panel(tmp_path, [("PDI", D, 0.221)], written_et=AFTER_NEXT_CLOSE)
    run(tmp_path, FakeClient([ev("PDI", 0.2205)]), p)
    r, = rows_of(tmp_path)
    assert r["distribution_pnl_usd"] == "22.05" and r["auction_pnl_with_distributions_usd"] == ds.UNMEASURED


def test_no_positions_means_nothing_is_entitled_and_no_query(tmp_path):
    session(tmp_path, held={})
    c = FakeClient()
    run(tmp_path, c, tmp_path / "absent.parquet")
    assert rows_of(tmp_path)[0]["distribution_pnl_usd"] == "0.00" and c.calls == []


def test_a_day_with_no_session_folder_is_skipped(tmp_path):
    assert run(tmp_path, FakeClient(), tmp_path / "absent.parquet") == []


# ------------------------------------------------- inside verify, never the verdict

def test_verify_main_exits_0_on_a_pass_even_if_the_distribution_file_is_foreign(monkeypatch, tmp_path):
    """Review 2026-10-09: a failure inside a hook's error handling escaped main() and
    turned a PASS day into exit 1. Each hook is now guarded on its own."""
    from quantt.session.tests.test_verify import D as VD, FakeClient as VerifyClient, plan, log_lines
    monkeypatch.setenv("QUANTT_STATE_DIR", str(tmp_path))
    (tmp_path / VD.isoformat()).mkdir()                 # what test_verify's `state` fixture does
    plan(tmp_path, refusals=[("halt", "x")])
    (tmp_path / "distribution_scores.csv").write_text("a,b\n1,2\n")
    monkeypatch.setattr(vf, "_make_client", lambda book: VerifyClient())
    assert vf.main(["--book", "cef"]) == 0
    assert log_lines(tmp_path)[0].startswith("2026-09-29 PASS")


def test_verify_hook_skips_non_trading_days(tmp_path):
    vf.run_distributions(FakeClient(), tmp_path, dt.date(2026, 10, 10), book="cef")  # a Saturday
    assert not (tmp_path / "distribution_scores.csv").exists()


def test_dist_score_never_transmits():
    tree = ast.parse(inspect.getsource(ds))
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not (attrs | names) & {"submit_order", "post", "delete", "patch", "put", "request"}
