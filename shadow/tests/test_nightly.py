"""The nightly run: the as-of date is the latest CLOSED session, a failed refresh is loud,
marks are fetched only where missing, and a second run changes nothing. Fakes only."""
import datetime as dt
import json

import pandas as pd

from shadow import book as book_mod
from shadow import engine, nightly
from shadow.tests.test_engine import _days, _px, _state

NY = engine.NY


def _at(d, h, m=0):
    return dt.datetime.combine(d, dt.time(h, m), tzinfo=NY)


def test_asof_is_the_latest_closed_session():
    days = _days(5)                                   # Mon..Fri
    assert nightly.asof_session(days, _at(days[2], 18, 45)) == days[2]      # evening: today
    assert nightly.asof_session(days, _at(days[2], 7, 20)) == days[1]       # morning backstop: yesterday
    assert nightly.asof_session(days, _at(days[2], 16, 29)) == days[1]      # one minute before SETTLE
    sat = days[4] + dt.timedelta(days=1)
    assert nightly.asof_session(days, _at(sat, 9)) == days[4]
    assert nightly.asof_session(days, _at(days[0], 9)) is None


class FakeSrc:
    def __init__(self, px, days):
        self.px, self.days, self.calls = px, days, []

    def sessions(self, first, last):
        return [d for d in self.days if first <= d <= last]

    def prints(self, syms, day):
        self.calls.append(day)
        rows = self.px[(self.px["date"].dt.date == day) & self.px["symbol"].isin(syms)]
        return dict(zip(rows["symbol"], rows["close"]))

    def distributions(self, syms, first, last):
        return []


def _check(px):
    return lambda syms, a, b: px[["date", "symbol", "close"]]


def _book(tmp_path, days, refresh):
    f = tmp_path / "books" / "t1.json"
    f.parent.mkdir(exist_ok=True)
    f.write_text(json.dumps({
        "slug": "t1", "card": "none", "signal": "shadow.tests._signals:last_return", "fill": "next_close",
        "panels": {"px": {"path": "px.parquet", "date_col": "date", "required_asof": True}},
        "refresh": refresh, "notional_usd": 1_000_000, "started": days[1].isoformat(), "enabled": True}))
    return book_mod.load(f)


def test_nightly_decides_marks_and_is_safe_to_repeat(tmp_path):
    days = _days(8)
    px = _px(days, seed=11)
    st = _state(tmp_path, px)
    b = _book(tmp_path, days, [])
    src = FakeSrc(px, days)
    for d in days[1:]:
        assert nightly.run(st, [b], src, check=_check(px), now=_at(d, 18, 45)) == 0
    sc = pd.read_csv(st / "t1" / "scores.csv")
    assert (sc["status"] == "SCORED").sum() == len(days) - 3      # first fill, then one row a session
    assert "SIMULATED" in (st / "SCOREBOARD.md").read_text()
    n_calls, marks_before = len(src.calls), (st / "marks.parquet").read_bytes()
    assert nightly.run(st, [b], src, check=_check(px), now=_at(days[-1], 20, 45)) == 0
    assert len(src.calls) == n_calls                              # nothing missing, nothing fetched
    assert (st / "marks.parquet").read_bytes() == marks_before
    assert len(pd.read_csv(st / "t1" / "scores.csv")) == len(sc)


def test_a_failed_refresh_is_reported_and_the_run_exits_nonzero(tmp_path, capsys):
    days = _days(5)
    px = _px(days)
    st = _state(tmp_path, px)
    b = _book(tmp_path, days, [["python3", "-c", "import sys; sys.exit(7)"]])
    rc = nightly.run(st, [b], FakeSrc(px, days), check=_check(px), now=_at(days[3], 18, 45))
    assert rc == 3 and "REFRESH FAILED (7)" in capsys.readouterr().out


def test_a_held_name_with_no_print_is_a_logged_gap_and_an_unmeasured_session(tmp_path):
    days = _days(8)
    px = _px(days, seed=13)
    st = _state(tmp_path, px)
    b = _book(tmp_path, days, [])
    holes = px[~((px["symbol"] == "DDD") & (px["date"].dt.date == days[5]))]
    src = FakeSrc(holes, days)
    rcs = [nightly.run(st, [b], src, check=_check(px), now=_at(d, 18, 45)) for d in days[1:]]
    assert 3 in rcs
    assert "DDD" in (st / "marks_gaps.csv").read_text()
    sc = pd.read_csv(st / "t1" / "scores.csv").set_index("date")
    assert sc.at[str(days[5]), "status"] == "UNMEASURED"


# ---- a book whose names change (2026-11-14): marks are asked for only where a decision holds the name

class RecordingSrc(FakeSrc):
    def prints(self, syms, day):
        self.calls.append((day, tuple(sorted(syms))))
        rows = self.px[(self.px["date"].dt.date == day) & self.px["symbol"].isin(syms)]
        return dict(zip(rows["symbol"], rows["close"]))


def _decision(st, slug, asof, weights):
    d = st / slug / "decisions"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{asof}.json").write_text(json.dumps({"asof": asof.isoformat(), "weights": weights}))


def test_a_name_is_marked_only_while_a_decision_holds_it(tmp_path):
    days = _days(10)
    px = _px(days, seed=3)                                          # AAA..EEE print every day
    st = tmp_path / "state"
    st.mkdir()
    b = _book(tmp_path, days, [])
    _decision(st, "t1", days[1], {"AAA": 1.0})
    _decision(st, "t1", days[2], {"AAA": 1.0})
    _decision(st, "t1", days[3], {"BBB": 1.0})                      # AAA dropped, BBB new
    for d in days[4:9]:
        _decision(st, "t1", d, {"BBB": 1.0})
    src = RecordingSrc(px, days)
    assert nightly.update_marks(st, [b], src, _check(px), days, days[8]) == 0
    asked = {}
    for day, syms in src.calls:
        for s in syms:
            asked.setdefault(s, set()).add(day)
    # AAA: from its first decision to two sessions after the decision that replaced it
    assert asked["AAA"] == set(days[1:6])
    # BBB: never asked for before the decision that first named it
    assert asked["BBB"] == set(days[3:9])
    assert set(asked) == {"AAA", "BBB"}


def test_the_latest_decision_is_held_until_replaced_so_its_names_stay_needed(tmp_path):
    days = _days(8)
    px = _px(days, seed=4)
    st = tmp_path / "state"
    st.mkdir()
    b = _book(tmp_path, days, [])
    _decision(st, "t1", days[1], {"CCC": 1.0})                      # then the book stops deciding
    src = RecordingSrc(px, days)
    nightly.update_marks(st, [b], src, _check(px), days, days[6])
    assert {day for day, _ in src.calls} == set(days[1:7])


def test_an_old_gap_is_not_asked_for_again_after_the_retry_window(tmp_path):
    days = _days(10)
    px = _px(days, seed=5)
    holes = px[~((px["symbol"] == "DDD") & (px["date"].dt.date == days[2]))]
    st = tmp_path / "state"
    st.mkdir()
    b = _book(tmp_path, days, [])
    src = RecordingSrc(holes, days)
    asked_for_hole = []
    for k in range(1, 9):
        _decision(st, "t1", days[k], {"DDD": 1.0})
        before = len(src.calls)
        nightly.update_marks(st, [b], src, _check(px), days, days[k])
        asked_for_hole.append(any(day == days[2] for day, _ in src.calls[before:]))
    # asked on its own night and while it is among the last GAP_RETRY_SESSIONS sessions, never after
    assert asked_for_hole == [False, True, True, True, False, False, False, False]
    gaps = (st / "marks_gaps.csv").read_text().splitlines()
    assert len(gaps) == 2 and "DDD" in gaps[1]                      # header and ONE row: logged once


def test_one_books_bug_does_not_stop_the_books_after_it(tmp_path, capsys):
    """A signal that raises (not `Unmeasured`) used to leave nightly.run's loop, so every later
    book went without a decision that night. Now the broken book is named with its exception,
    the run exits 3, and the next book still decides. Fails on b2df5e5 (KeyError propagates)."""
    days = _days(5)
    px = _px(days)
    st = _state(tmp_path, px)
    good = _book(tmp_path, days, [])
    f = tmp_path / "books" / "a0.json"
    f.write_text(json.dumps({
        "slug": "a0", "card": "none", "signal": "shadow.tests._signals:boom", "fill": "next_close",
        "panels": {"px": {"path": "px.parquet", "date_col": "date", "required_asof": True}},
        "refresh": [], "notional_usd": 1_000_000, "started": days[1].isoformat(), "enabled": True}))
    bad = book_mod.load(f)
    rc = nightly.run(st, [bad, good], FakeSrc(px, days), check=_check(px), now=_at(days[3], 18, 45))
    out = capsys.readouterr().out
    assert rc == 3 and "decide a0" in out and "ERROR KeyError" in out
    assert f"decide t1 {days[3]}: DECIDED" in out
    assert (st / "t1" / "decisions" / f"{days[3]}.json").exists()
    assert not (st / "a0" / "decisions" / f"{days[3]}.json").exists()

