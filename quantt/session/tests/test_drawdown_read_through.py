"""The drawdown check read through an earlier session (quantt/session/drawdown.py `check(..., read_through=)`).

WHY (team lead's ruling 2026-11-03, E-2026-11-03-42, answering the owner's finding
E-2026-11-03-41). At prod's 22:00 decide the EOD row for the as-of D is never there yet: 4 of 4
core decides that carry the field read UNMEASURED because eod_equity.csv's newest row was D-1. CEF
trial 55's K0 builds a reduced book only on an exact OK, so it would have flattened every reduced
session. The ruling: K0 reads D-1's row, labelled one session stale; an older row, a missing or a
bad file is UNMEASURED. The owner of drawdown.py specified it as a parameter of the existing check,
None being today's reading byte for byte; only te4's K0 passes it (run.py `_thin_k0_drawdown`, and
tests/test_trade_eligible_runner.py in the session).

Each test here fails on the code before it (a323971), whose `check` takes no `read_through` and
raises TypeError. The None case is pinned two ways: equal to the call without the keyword, and
the existing tests/test_drawdown.py unchanged.

Dates are real NYSE sessions (the staleness is counted on ops/schedule/nyse_calendar.py, never on
weekdays): as-of Friday 2026-09-25, D-1 Thursday 09-24, D-2 Wednesday 09-23; and across
Thanksgiving, as-of Friday 2026-11-27 with D-1 Wednesday 11-25.
"""
import datetime as dt

import pytest

from quantt.session import drawdown as ddm

SPEC = {"spec_id": "test.read_through", "risk": {"halve_drawdown": 0.12, "kill_drawdown": 0.18}}
ASOF, D1, D2 = dt.date(2026, 9, 25), dt.date(2026, 9, 24), dt.date(2026, 9, 23)
HEAD = [(dt.date(2026, 9, 21), 100_000.0), (dt.date(2026, 9, 22), 101_000.0), (D2, 100_500.0)]


def write(state, rows, *, raw=None):
    """`<state>/eod_equity.csv` in the collector's shape (`change_usd` empty on the first row),
    or `raw` text as given."""
    state.mkdir(parents=True, exist_ok=True)
    p = state / ddm.OFFICIAL_FILE
    if raw is not None:
        p.write_text(raw)
        return p
    lines, prev = ["date,equity,change_usd"], None
    for d, e in rows:
        lines.append(f"{d.isoformat()},{e},{'' if prev is None else round(e - prev, 2)}")
        prev = e
    p.write_text("\n".join(lines) + "\n")
    return p


@pytest.mark.parametrize("d1_equity,status", [(100_600.0, ddm.OK), (87_000.0, ddm.HALVE),
                                              (80_000.0, ddm.KILL)])
def test_a_d_minus_1_row_gives_its_status_labelled_one_session_stale(tmp_path, d1_equity,
                                                                     status):
    """The 22:00 case: no row for the as-of; the row of the session before it gives the status,
    with the high-water mark over the rows on or before it (101,000 on 09-22)."""
    write(tmp_path, HEAD + [(D1, d1_equity)])
    r = ddm.check(tmp_path, SPEC, ASOF, ddm.REPORT, read_through=D1)
    assert r["status"] == status and "why" not in r
    assert r["asof"] == ASOF and r["read_through"] == D1
    assert r["reading"]["last_date"] == D1 and r["reading"]["hwm"] == 101_000.0
    assert r["reading"]["drawdown"] == pytest.approx(1 - d1_equity / 101_000.0, abs=1e-8)
    assert r["reading"]["stale"] == {"row_date": D1, "sessions": 1}
    assert r["would_on"] == ddm.WOULD_ON[status]


def test_the_asofs_own_row_is_not_read_when_reading_through_d_minus_1(tmp_path):
    """The morning backstop: the as-of's row is there. Read through D-1 it is not read at all:
    neither its level (a new high here, which would have set the HWM) nor its status."""
    write(tmp_path, HEAD + [(D1, 87_000.0), (ASOF, 120_000.0)])
    r = ddm.check(tmp_path, SPEC, ASOF, ddm.REPORT, read_through=D1)
    assert r["status"] == ddm.HALVE and r["reading"]["hwm"] == 101_000.0
    assert r["reading"]["rows"] == 4
    assert ddm.check(tmp_path, SPEC, ASOF, ddm.REPORT)["status"] == ddm.OK   # the as-of reading


def test_a_newest_row_older_than_d_minus_1_is_unmeasured(tmp_path):
    """D-2 only: UNMEASURED, naming both dates; the stale figures stay recorded, labelled two
    sessions stale (the as-of reading would say the same thing of the as-of)."""
    write(tmp_path, HEAD)
    r = ddm.check(tmp_path, SPEC, ASOF, ddm.REPORT, read_through=D1)
    assert r["status"] == ddm.UNMEASURED
    assert f"read-through date {D1} is {D2}, not {D1}" in r["why"]
    assert r["reading"]["stale"] == {"row_date": D2, "sessions": 2}
    assert r["would_on"] == ddm.WOULD_ON[ddm.UNMEASURED]


@pytest.mark.parametrize("case", ["missing", "bad equity", "bad date", "no header column",
                                  "repeated date"])
def test_a_missing_or_bad_file_is_unmeasured(tmp_path, case):
    good = "date,equity,change_usd\n2026-09-22,101000.0,\n"
    raw = {"missing": None,
           "bad equity": good + "2026-09-24,abc,1\n",
           "bad date": good + "09/24/2026,100600.0,1\n",
           "no header column": "date,value\n2026-09-24,100600.0\n",
           "repeated date": good + "2026-09-24,100600.0,1\n2026-09-24,100600.0,0\n"}[case]
    if raw is not None:
        write(tmp_path, None, raw=raw)
    r = ddm.check(tmp_path, SPEC, ASOF, ddm.REPORT, read_through=D1)
    assert r["status"] == ddm.UNMEASURED and r["read_through"] == D1, r
    assert ddm.OFFICIAL_FILE in r["why"]


def test_read_through_none_is_the_as_of_reading_unchanged(tmp_path):
    """None is today's check, byte for byte: the same record as the call without the keyword,
    on a series that ends on the as-of, on one that ends a session early, and with no file."""
    for rows in (HEAD + [(D1, 100_600.0), (ASOF, 87_000.0)], HEAD + [(D1, 100_600.0)], None):
        state = tmp_path / str(len(rows or ()))
        state.mkdir()
        if rows is not None:
            write(state, rows)
        old = ddm.check(state, SPEC, ASOF, ddm.REPORT)
        assert ddm.check(state, SPEC, ASOF, ddm.REPORT, read_through=None) == old
        assert "read_through" not in old and "stale" not in old.get("reading", {})


def test_staleness_counts_nyse_sessions_not_weekdays(tmp_path):
    """Across Thanksgiving (Thursday 2026-11-26, closed): the session before Friday 11-27 is
    Wednesday 11-25, one session stale; a row of Tuesday 11-24 is two."""
    asof, wed, tue = dt.date(2026, 11, 27), dt.date(2026, 11, 25), dt.date(2026, 11, 24)
    write(tmp_path, [(dt.date(2026, 11, 23), 100_000.0), (tue, 100_100.0), (wed, 100_200.0)])
    r = ddm.check(tmp_path, SPEC, asof, ddm.REPORT, read_through=wed)
    assert r["status"] == ddm.OK and r["reading"]["stale"] == {"row_date": wed, "sessions": 1}
    assert ddm.sessions_after(tue, asof) == 2 and ddm.sessions_after(asof, asof) == 0


def test_a_read_through_date_after_the_as_of_raises():
    """No lookahead: a caller bug, raised, never read."""
    with pytest.raises(ValueError, match="lookahead"):
        ddm.check("/nonexistent", SPEC, ASOF, ddm.REPORT, read_through=ASOF + dt.timedelta(1))
