"""quantt/collect: the data day, idempotent steps, flags vs gaps, and read-only at the broker.

What these pin (the collector's brief, team lead 2026-09-29):
  * D is the latest day BOTH calendars call trading whose close + 45 min has
    passed by Alpaca's clock; a calendar disagreement raises naming both.
  * A completed step is never redone, a failed one is retried, and a day whose
    steps are all ok is one IDLE line with no network beyond clock + calendar.
  * Cross-check disagreements are FLAGS and never fail anything (report only);
    a value a source does not have is a GAP, never a substitute.
  * The official-close file is de-duplicated on (date, ticker).
  * The package never names the client's transmit method.

Hermetic: `FakeClient` has only GETs (no transmit method at all), subprocesses
and CEFConnect are injected fakes, panels and state live under tmp_path, and
the root conftest's netguard refuses any socket.
"""
import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

from ops.schedule.nyse_calendar import is_trading_day
from quantt.broker import alpaca as al
from quantt.collect import collect as co

ET = co.ET
D = dt.date(2026, 9, 29)            # Tuesday
PREV = dt.date(2026, 9, 28)         # Monday
NEXT = dt.date(2026, 9, 30)
DEPLOYED = ["AAA", "BBB"]
UNIVERSE = ["AAA", "BBB", "CCC"]


def et(day, h, m=0):
    return dt.datetime.combine(day, dt.time(h, m), ET)


def eod_stamp(day):
    """00:00 UTC of the next calendar day: Alpaca's stamp for `day`'s EOD point."""
    return dt.datetime.combine(day + dt.timedelta(days=1), dt.time(0), tzinfo=dt.timezone.utc)


class FakeClient:
    """The GET surface of AlpacaClient in its parsed shapes. No transmit method."""

    def __init__(self, *, now=None, is_open=False, next_open=None, extra_days=(),
                 missing_days=(), prints=None):
        self.now = now or et(D, 21, 0)
        self.is_open = is_open
        self.next_open = next_open or et(NEXT, 9, 30)
        self.extra, self.missing = set(extra_days), set(missing_days)
        self.prints = {"AAA": 9.50, "BBB": 19.00, "CCC": 5.00} if prints is None else prints
        self.calls = []
        self.superseded = {}

    def clock(self):
        self.calls.append("clock")
        return {"timestamp": self.now, "is_open": self.is_open, "next_open": self.next_open,
                "next_close": self.next_open + dt.timedelta(hours=6, minutes=30), "raw": {}}

    def calendar(self, start, end):
        self.calls.append("calendar")
        out, d = [], start
        while d <= end:
            if (is_trading_day(d) or d in self.extra) and d not in self.missing:
                out.append({"date": d, "open": "09:30", "close": "16:00", "raw": {}})
            d += dt.timedelta(days=1)
        return out

    def stock_exchanges(self):
        self.calls.append("exchanges")
        return {"N": "New York Stock Exchange"}

    def primary_sip_code(self, symbol, exchanges):
        return "N"

    def closing_auction_prints(self, symbols, date, *, exchange_codes, condition="M"):
        assert len(symbols) == 1 and exchange_codes == {symbols[0]: "N"} and condition == "M"
        self.calls.append(("prints", symbols[0]))
        p = self.prints.get(symbols[0])
        if p is None:
            raise al.MissingAuctionPrint(f"no print for {symbols}", symbols=list(symbols))
        out = {"price": p, "exchange": "N", "condition": "M", "t": "2026-09-29T20:00:01Z"}
        if symbols[0] in self.superseded:
            out["superseded"] = self.superseded[symbols[0]]
        return {symbols[0]: out}

    def account(self):
        self.calls.append("account")
        return {"id": "acct", "status": "ACTIVE", "equity": 100_500.0, "last_equity": 100_000.0,
                "cash": 50_000.0, "long_market_value": 80_000.0,
                "short_market_value": -29_500.0, "raw": {"api_key_echo": "SHOULD-NOT-APPEAR"},
                "auth_token": "SHOULD-NOT-APPEAR"}

    def positions(self):
        self.calls.append("positions")
        return al.Positions(qty={"AAA": 100, "BBB": -50}, raw=[])

    def orders(self, *, status, after=None, until=None, limit=500, nested=False):
        assert status == "all"
        self.calls.append(("orders", after))
        return []

    def activities_fills(self, date):
        self.calls.append(("fills", date))
        return []

    # Alpaca's EOD history, {date: equity}. None = the default synthetic series: every
    # trading day from 2026-09-28, 100,000 + 10 a session. A test may set a dict.
    eod = None

    def eod_equity_history(self, start, end):
        """The client's parsed shape: EODPoints stamped 00:00 UTC after each session,
        as Alpaca stamped them in the 2026-10-19 read (20:00 ET in summer)."""
        self.calls.append(("eod", start, end))
        if self.eod is None:
            series, d, i = {}, dt.date(2026, 9, 28), 0
            while d <= end:
                if is_trading_day(d):
                    series[d] = 100_000.0 + 10 * i
                    i += 1
                d += dt.timedelta(days=1)
        else:
            series = self.eod
        return [al.EODPoint(d, eq, eod_stamp(d)) for d, eq in sorted(series.items())
                if start <= d <= end]

    # Borrow flags by symbol; a test may replace `self.flags` to change a day.
    flags = {"AAA": (True, True, True), "BBB": (True, True, True), "ZZZ": (True, False, False)}

    def assets(self, *, status="active", asset_class="us_equity"):
        assert status == "active" and asset_class == "us_equity"
        self.calls.append("assets")
        return [{"symbol": s, "exchange": "NYSE", "status": "active", "tradable": tr,
                 "shortable": sh, "marginable": True, "fractionable": False,
                 "easy_to_borrow": etb, "borrow_status": "easy_to_borrow" if etb else "hard_to_borrow",
                 "maintenance_margin_requirement": 30.0, "margin_requirement_long": 30.0,
                 "margin_requirement_short": 30.0}
                for s, (tr, sh, etb) in sorted(self.flags.items())]


class FakeRun:
    def __init__(self, codes=None):
        self.codes = {"fetch_daily.py": 0, "fetch_cef_distributions.py": 0, **(codes or {})}
        self.cmds = []

    def __call__(self, cmd, timeout_s):
        self.cmds.append(cmd)
        name = Path(cmd[1]).name
        return self.codes[name], f"{name} output"


def write_panels(cef, *, nav=None, close=None):
    nav = nav or {"AAA": 10.00, "BBB": 20.00}
    close = close or {"AAA": 9.50, "BBB": 19.00}
    pd.DataFrame([{"date": pd.Timestamp(D), "nav": v, "ticker": t} for t, v in nav.items()]
                 ).to_parquet(cef / "cef_nav.parquet")
    pd.DataFrame([{"date": pd.Timestamp(D), "open": v, "high": v, "low": v, "close": v,
                   "volume": 1, "ticker": t, "grp": "x"} for t, v in close.items()]
                 ).to_parquet(cef / "cef_prices.parquet")
    pd.DataFrame({"ticker": UNIVERSE, "grp": "x"}).to_csv(cef / "cef_universe.csv", index=False)


@pytest.fixture
def env(tmp_path):
    state, cef = tmp_path / "state", tmp_path / "cef"
    state.mkdir()
    cef.mkdir()
    write_panels(cef)
    return state, cef


def make_ctx(env, client=None, run=None, cc=None, cc_day=D):
    state, cef = env
    cc = {"AAA": 10.00, "BBB": 20.00} if cc is None else cc

    def cefconnect(t, day):
        assert day == cc_day
        v = cc[t]
        if isinstance(v, Exception):
            raise v
        return v

    return co.Ctx(book="cef", client=client or FakeClient(), state_dir=state, cef_dir=cef,
                  repo=Path("/nonexistent"), book_path="ops/books/cef_discount_book.json",
                  deployed=list(DEPLOYED), run=run or FakeRun(), cefconnect_nav=cefconnect)


def status(env, day=D):
    return json.loads((env[0] / "data" / day.isoformat() / "status.json").read_text())


def log_lines(env):
    p = env[0] / "data.log"
    return p.read_text().splitlines() if p.exists() else []


# ------------------------------------------------------------------ the data day

@pytest.mark.parametrize("now, want", [
    (et(D, 16, 44), PREV),                 # before close + 45 min: the previous day
    (et(D, 16, 45), D),                    # exactly ready
    (et(D, 9, 0), PREV),                   # morning: yesterday
    (et(dt.date(2026, 10, 3), 12), dt.date(2026, 10, 2)),   # Saturday -> Friday
    (et(dt.date(2026, 10, 5), 10), dt.date(2026, 10, 2)),   # Monday morning -> Friday
])
def test_data_day(now, want):
    assert co.data_day(FakeClient(now=now))[0] == want


def test_calendars_disagree_raises_naming_both():
    # Alpaca calls Monday closed; nyse_calendar calls it trading.
    with pytest.raises(co.CalendarDisagreement, match=r"2026-09-28.*Alpaca.*closed.*nyse_calendar.*trading"):
        co.data_day(FakeClient(now=et(D, 9, 0), missing_days={PREV}))
    # And the other way: Alpaca trades a Saturday.
    sat = dt.date(2026, 10, 3)
    with pytest.raises(co.CalendarDisagreement, match="Alpaca /v2/calendar says trading"):
        co.data_day(FakeClient(now=et(sat, 12), extra_days={sat}))


# ------------------------------------------------------------------ idempotency

def test_complete_run_then_idle_with_no_further_network(env, capsys):
    client, run = FakeClient(), FakeRun()
    ctx = make_ctx(env, client, run)
    assert co.collect(ctx) == co.EXIT_OK
    s = status(env)
    assert all(s["steps"][k]["ok"] for k in co.STEPS), s
    assert all({"ok", "err", "detail", "at"} <= set(s["steps"][k]) for k in co.STEPS)
    assert log_lines(env) == [f"{D} DATA COMPLETE flags=0 gaps=0"]
    report = json.loads((env[0] / "data" / D.isoformat() / "report.json").read_text())
    assert report["complete"] and report["failed_steps"] == []

    client.calls.clear()
    n_cmds = len(run.cmds)
    capsys.readouterr()
    assert co.collect(make_ctx(env, client, run)) == co.EXIT_OK
    assert capsys.readouterr().out.strip() == f"IDLE {D} complete"
    assert client.calls == ["clock", "calendar"], "an idle run made more than the D lookup"
    assert len(run.cmds) == n_cmds
    assert len(log_lines(env)) == 1, "an idle run must not write a data.log line"


def test_failed_step_is_retried_and_completed_steps_are_not_redone(env):
    client, run = FakeClient(), FakeRun({"fetch_daily.py": 4})
    assert co.collect(make_ctx(env, client, run)) == co.EXIT_INCOMPLETE
    s = status(env)
    assert not s["steps"]["prices_nav"]["ok"] and "exited 4" in s["steps"]["prices_nav"]["err"]
    assert s["steps"]["nav_crosscheck"]["err"] == "waiting on prices_nav"
    assert s["steps"]["official_closes"]["ok"] and s["steps"]["account_snapshot"]["ok"]
    assert log_lines(env) == [f"{D} DATA INCOMPLETE prices_nav,nav_crosscheck,"
                              f"close_crosscheck flags=0 gaps=0"]

    client.calls.clear()
    run.codes["fetch_daily.py"] = 0
    n_before = len(run.cmds)
    assert co.collect(make_ctx(env, client, run)) == co.EXIT_OK
    names = [Path(c[1]).name for c in run.cmds[n_before:]]
    assert names == ["fetch_daily.py"], "distributions re-ran although it was ok"
    assert not [c for c in client.calls if c in ("account", "positions")
                or (isinstance(c, tuple) and c[0] == "prints")], client.calls
    assert log_lines(env)[-1] == f"{D} DATA COMPLETE flags=0 gaps=0"


def test_fetch_daily_is_run_with_the_sessions_flags(env):
    run = FakeRun()
    co.collect(make_ctx(env, run=run))
    cmd = next(c for c in run.cmds if c[1].endswith("fetch_daily.py"))
    assert "--nav-fallback" not in cmd      # CEFConnect stays independent (review 2026-09-29)
    assert cmd[2:] == ["--require-asof", D.isoformat(),
                       "--book", "ops/books/cef_discount_book.json"]


def test_timeout_is_a_failed_step(env):
    class Hang(FakeRun):
        def __call__(self, cmd, timeout_s):
            self.cmds.append(cmd)
            return (None, "hung") if cmd[1].endswith("fetch_daily.py") else (0, "")
    assert co.collect(make_ctx(env, run=Hang())) == co.EXIT_INCOMPLETE
    assert "timed out" in status(env)["steps"]["prices_nav"]["err"]


# ------------------------------------------------------------------ flags vs gaps

def test_disagreements_are_flags_and_never_fail_the_run(env):
    state, cef = env
    write_panels(cef, close={"AAA": 9.50, "BBB": 19.10})     # BBB panel close 19.10 vs print 19.00
    ctx = make_ctx(env, cc={"AAA": 10.02, "BBB": 20.00})      # AAA CEFConnect 10.02 vs panel 10.00
    assert co.collect(ctx) == co.EXIT_OK, "a flag must never fail the run (report only)"
    report = json.loads((state / "data" / D.isoformat() / "report.json").read_text())
    flags = {(f["step"], f["fund"]): f for f in report["flags"]}
    assert set(flags) == {("nav_crosscheck", "AAA"), ("close_crosscheck", "BBB")}
    f = flags[("nav_crosscheck", "AAA")]
    assert (f["value_a"], f["value_b"]) == (10.00, 10.02)
    assert {"fund", "source_a", "value_a", "source_b", "value_b"} <= set(f)
    assert log_lines(env)[-1] == f"{D} DATA COMPLETE flags=2 gaps=0"


def test_a_half_cent_is_not_a_flag(env):
    ctx = make_ctx(env, cc={"AAA": 10.004, "BBB": 20.00})
    co.collect(ctx)
    assert status(env)["steps"]["nav_crosscheck"]["detail"]["flags"] == []


def test_cefconnect_without_d_is_a_gap_not_a_flag(env):
    ctx = make_ctx(env, cc={"AAA": None, "BBB": 20.00})
    assert co.collect(ctx) == co.EXIT_OK
    d = status(env)["steps"]["nav_crosscheck"]
    assert d["ok"] and d["detail"]["flags"] == []
    assert [g["fund"] for g in d["detail"]["gaps"]] == ["AAA"]


def test_a_repeat_with_no_cefconnect_row_is_a_flag_not_a_gap(env):
    """2026-10-13. At ~21:40 ET CEFConnect has no row for D, and on 6 of 7 laptop
    data days this step recorded 13 gaps while Yahoo served rows dated D that
    carried D-1's NAV (results/cef/LIVE_NAV_QUALITY_2026-10-12.md §5). A NAV(D)
    equal to the previous row with nothing to confirm it is now a FLAG naming
    both values; a NAV that moved is still a gap."""
    state, cef = env
    pd.DataFrame([{"date": pd.Timestamp(d), "nav": v, "ticker": t}
                  for t, d, v in (("AAA", PREV, 10.00), ("AAA", D, 10.00),
                                  ("BBB", PREV, 19.50), ("BBB", D, 20.00))]
                 ).to_parquet(cef / "cef_nav.parquet")
    assert co.collect(make_ctx(env, cc={"AAA": None, "BBB": None})) == co.EXIT_OK
    d = status(env)["steps"]["nav_crosscheck"]
    assert d["ok"]
    (f,) = d["detail"]["flags"]
    assert (f["fund"], f["check"], f["value_a"], f["value_b"]) == \
        ("AAA", "nav_repeat_unverified", 10.00, 10.00)
    assert PREV.isoformat() in f["source_b"] and "unverified" in f["reason"]
    assert [g["fund"] for g in d["detail"]["gaps"]] == ["BBB"]
    rep = json.loads((state / "data" / D.isoformat() / "report.json").read_text())
    assert [x["fund"] for x in rep["flags"] if x["step"] == "nav_crosscheck"] == ["AAA"]


def test_a_repeat_cefconnect_confirms_is_neither_flag_nor_gap(env):
    state, cef = env
    pd.DataFrame([{"date": pd.Timestamp(d), "nav": v, "ticker": t}
                  for t, d, v in (("AAA", PREV, 10.00), ("AAA", D, 10.00),
                                  ("BBB", PREV, 20.00), ("BBB", D, 20.00))]
                 ).to_parquet(cef / "cef_nav.parquet")
    co.collect(make_ctx(env, cc={"AAA": 10.00, "BBB": 20.03}))
    d = status(env)["steps"]["nav_crosscheck"]["detail"]
    assert d["gaps"] == []
    assert [(f["fund"], f.get("check")) for f in d["flags"]] == [("BBB", None)]   # a stale copy


def test_cefconnect_arrival_is_logged_when_each_row_first_appears(env):
    """2026-10-13: when CEFConnect publishes D decides how often the session's
    stale-NAV gate must hold a name, and the evidence was three readings. Each
    slot polls the names not yet seen; a first sighting is logged with the last
    reading that did not have it. A WATCH step: it never makes the day
    INCOMPLETE, and the collector idles once every row has arrived."""
    state, cef = env
    cc = {"AAA": None, "BBB": 20.00}
    assert co.collect(make_ctx(env, cc=cc)) == co.EXIT_OK          # complete, still watching
    st = status(env)["steps"]["cefconnect_arrival"]
    assert not st["ok"] and "AAA" in st["err"]
    assert co.log_line(json.loads((state / "data" / D.isoformat() / "report.json").read_text())
                       ).endswith("watching=cefconnect_arrival")
    rows = pd.read_csv(state / co.ARRIVAL_FILE, keep_default_na=False)
    assert rows[["date", "ticker", "polls", "nav"]].values.tolist() == [[D.isoformat(), "BBB", 1, 20.0]]
    assert rows.loc[0, "last_absent_utc"] == ""                     # seen on the first poll
    cc["AAA"] = 10.00                                                # the row arrives
    client = FakeClient()
    assert co.collect(make_ctx(env, client, cc=cc)) == co.EXIT_OK
    rows = pd.read_csv(state / co.ARRIVAL_FILE, keep_default_na=False)
    assert rows["ticker"].tolist() == ["BBB", "AAA"]
    a = rows.iloc[1]
    assert a["polls"] == 2 and a["last_absent_utc"] and a["last_absent_utc"] <= a["first_seen_utc"]
    assert status(env)["steps"]["cefconnect_arrival"]["ok"]
    idle = FakeClient()
    assert co.collect(make_ctx(env, idle, cc=cc)) == co.EXIT_OK
    assert idle.calls == ["clock", "calendar"]                      # idle: nothing polled
    assert len(pd.read_csv(state / co.ARRIVAL_FILE)) == 2           # nothing logged twice


@pytest.mark.parametrize("content", ["", "a,b\n"], ids=["empty", "old_header"])
def test_a_bad_arrival_file_is_moved_aside_and_the_slot_still_logs(env, content):
    """quant-reviewer 2026-10-14: an empty cefconnect_arrival.csv (a kill before
    the first flush) or one with another header failed the step on every slot,
    with an empty detail -- the arrival measurement silently stopped. It is now
    moved aside whole, both files are named in the detail, and a new file takes
    this slot's arrivals."""
    state, cef = env
    (state / co.ARRIVAL_FILE).write_text(content)
    assert co.collect(make_ctx(env, cc={"AAA": None, "BBB": 20.00})) == co.EXIT_OK
    d = status(env)["steps"]["cefconnect_arrival"]["detail"]
    (aside,) = state.glob("cefconnect_arrival.csv.*.unreadable")
    assert aside.read_text() == content
    (note,) = d["file_rotations"]
    assert co.ARRIVAL_FILE in note and aside.name in note
    assert d["first_seen"]["BBB"]["nav"] == 20.0 and "AAA" in d["last_absent_utc"]
    rows = pd.read_csv(state / co.ARRIVAL_FILE, keep_default_na=False)
    assert tuple(rows.columns) == co.ARRIVAL_COLUMNS and rows["ticker"].tolist() == ["BBB"]


def test_cefconnect_unreadable_fails_the_step_so_it_is_retried(env):
    ctx = make_ctx(env, cc={"AAA": co.CefConnectError("AAA: ConnectionError"), "BBB": 20.0})
    assert co.collect(ctx) == co.EXIT_INCOMPLETE
    d = status(env)["steps"]["nav_crosscheck"]
    assert not d["ok"] and d["detail"]["fetch_errors"] == ["AAA: ConnectionError"]


# ------------------------------------------------- CEFConnect down (2026-10-29)

def refused(ticker, cause=None):
    """A CefConnectError exactly as the shared reader raises it (`nav_gate._wrap`,
    `from` the cause): by default the JSONDecodeError CEFConnect has answered
    every scripted request from the VM with since 2026-10-21."""
    from quantt.session import nav_gate as ng
    cause = cause if cause is not None else json.JSONDecodeError("Expecting value", "<html>", 0)

    def boom():
        raise cause
    try:
        ng._wrap(ticker, boom)
    except co.CefConnectError as e:
        return e
    raise AssertionError("nav_gate._wrap did not raise")


def test_cefconnect_refusing_every_name_is_second_source_unavailable_not_incomplete(env):
    """Every request refused: a distinct status, the collector exits 0, nothing is
    compared, flagged or filled; the step is retried, and compares the slot
    CEFConnect answers again. On bd87144 this run exited 5 (INCOMPLETE)."""
    ctx = make_ctx(env, cc={"AAA": refused("AAA"), "BBB": refused("BBB")})
    assert co.collect(ctx) == co.EXIT_OK
    want = "second source unavailable (cefconnect: JSONDecodeError)"
    st = status(env)["steps"]["nav_crosscheck"]
    assert not st["ok"] and st["unavailable"] == want and st["err"] == want
    assert st["detail"]["second_source"] == want
    assert st["detail"]["flags"] == [] and st["detail"]["gaps"] == []      # nothing faked
    assert [e.split(":")[0] for e in st["detail"]["fetch_errors"]] == ["AAA", "BBB"]
    report = json.loads((env[0] / "data" / D.isoformat() / "report.json").read_text())
    assert report["complete"] and report["failed_steps"] == []
    assert report["unavailable"] == {"nav_crosscheck": want}
    # (the arrival WATCH reads the same refusing CEFConnect, so it is still watching)
    assert log_lines(env)[-1] == (f"{D} DATA COMPLETE flags=0 gaps=0 watching=cefconnect_arrival"
                                  f"; nav_crosscheck: {want}")
    # Retried next slot: CEFConnect is back, and disagrees on AAA -- a real flag.
    assert co.collect(make_ctx(env, cc={"AAA": 10.02, "BBB": 20.00})) == co.EXIT_OK
    st = status(env)["steps"]["nav_crosscheck"]
    assert st["ok"] and "unavailable" not in st
    assert [(f["fund"], f["value_a"], f["value_b"]) for f in st["detail"]["flags"]] == \
        [("AAA", 10.00, 10.02)]
    report = json.loads((env[0] / "data" / D.isoformat() / "report.json").read_text())
    assert "unavailable" not in report
    assert log_lines(env)[-1] == f"{D} DATA COMPLETE flags=1 gaps=0"


def test_a_mixed_outage_names_every_error_class(env):
    import requests
    ctx = make_ctx(env, cc={"AAA": refused("AAA"),
                            "BBB": refused("BBB", requests.ConnectionError("reset"))})
    assert co.collect(ctx) == co.EXIT_OK
    assert status(env)["steps"]["nav_crosscheck"]["unavailable"] == \
        "second source unavailable (cefconnect: ConnectionError, JSONDecodeError)"


def test_one_name_refused_is_still_a_failed_step_as_today(env):
    """One fund's error is not an outage: the step fails and the day is
    INCOMPLETE, exactly as before (same error class as the outage's)."""
    ctx = make_ctx(env, cc={"AAA": refused("AAA"), "BBB": 20.00})
    assert co.collect(ctx) == co.EXIT_INCOMPLETE
    st = status(env)["steps"]["nav_crosscheck"]
    assert not st["ok"] and "unavailable" not in st and "second_source" not in st["detail"]
    assert st["err"] == "CEFConnect unreadable for 1 fund(s)"
    assert log_lines(env)[-1].startswith(f"{D} DATA INCOMPLETE nav_crosscheck ")


def test_a_lone_name_asked_and_refused_is_not_read_as_an_outage(env):
    """Only one name reached CEFConnect (the other is a panel gap): one error is
    one error, never an outage."""
    state, cef = env
    write_panels(cef, nav={"BBB": 20.00})                  # AAA: no NAV dated D
    ctx = make_ctx(env, cc={"AAA": 10.00, "BBB": refused("BBB")})
    assert co.collect(ctx) == co.EXIT_INCOMPLETE
    st = status(env)["steps"]["nav_crosscheck"]
    assert not st["ok"] and "unavailable" not in st
    assert [g["fund"] for g in st["detail"]["gaps"]] == ["AAA"]


def test_a_real_disagreement_beside_an_error_is_still_flagged_and_still_incomplete(env):
    ctx = make_ctx(env, cc={"AAA": 10.02, "BBB": refused("BBB")})
    assert co.collect(ctx) == co.EXIT_INCOMPLETE
    st = status(env)["steps"]["nav_crosscheck"]
    assert "unavailable" not in st
    assert [(f["fund"], f["value_a"], f["value_b"]) for f in st["detail"]["flags"]] == \
        [("AAA", 10.00, 10.02)]


def test_a_nav_the_panel_took_from_cefconnect_is_not_counted_as_agreement(env):
    state, cef = env
    pd.DataFrame([{"date": D.isoformat(), "nav": 10.0, "ticker": "AAA", "source": "cefconnect",
                   "written_utc": "x"}]).to_csv(cef / "nav_fallback_log.csv", index=False)
    co.collect(make_ctx(env))
    gaps = status(env)["steps"]["nav_crosscheck"]["detail"]["gaps"]
    assert [g["fund"] for g in gaps] == ["AAA"] and "not an independent" in gaps[0]["reason"]


def test_missing_print_for_a_non_deployed_name_is_a_gap_only(env):
    client = FakeClient(prints={"AAA": 9.50, "BBB": 19.00})          # CCC has none
    assert co.collect(make_ctx(env, client)) == co.EXIT_OK
    d = status(env)["steps"]["official_closes"]
    assert d["ok"] and [g["fund"] for g in d["detail"]["gaps"]] == ["CCC"]


def test_a_transient_error_on_a_non_deployed_name_is_retried_not_a_gap(env):
    # review 2026-09-29: a 5xx used to become a permanent hole in the file
    client = FakeClient()
    real = client.closing_auction_prints

    def flaky(symbols, date, **kw):
        if symbols[0] == "CCC":
            raise al.AlpacaHTTPError("GET /v2/stocks/auctions -> HTTP 503", status=503)
        return real(symbols, date, **kw)
    client.closing_auction_prints = flaky
    assert co.collect(make_ctx(env, client)) == co.EXIT_INCOMPLETE
    d = status(env)["steps"]["official_closes"]
    assert not d["ok"] and d["detail"]["gaps"] == []
    assert "CCC" in d["detail"]["transient_errors"][0]
    client.closing_auction_prints = real                             # next slot: it answers
    co.collect(make_ctx(env, client))
    assert status(env)["steps"]["official_closes"]["ok"]


def test_missing_print_for_a_deployed_name_fails_the_step(env):
    client = FakeClient(prints={"AAA": 9.50, "CCC": 5.00})           # BBB is deployed
    assert co.collect(make_ctx(env, client)) == co.EXIT_INCOMPLETE
    d = status(env)["steps"]["official_closes"]
    assert not d["ok"] and "BBB" in d["err"]
    assert status(env)["steps"]["close_crosscheck"]["err"] == "waiting on official_closes"


def test_auction_is_not_queried_before_1645_et(env):
    # An early close (13:00) makes D ready at 13:45, but the print window ends 16:30.
    client = FakeClient(now=et(D, 14, 0))
    client.calendar = lambda s, e: [{"date": d, "open": "09:30",
                                     "close": "13:00" if d == D else "16:00", "raw": {}}
                                    for d in pd.date_range(s, e).date if is_trading_day(d)]
    assert co.collect(make_ctx(env, client)) == co.EXIT_INCOMPLETE
    assert "16:45" in status(env)["steps"]["official_closes"]["err"]
    assert not [c for c in client.calls if isinstance(c, tuple) and c[0] == "prints"]


# ------------------------------------------------------------------ the parquet

def test_official_close_file_is_deduplicated_and_not_refetched(env):
    state, cef = env
    pd.DataFrame([
        {"date": pd.Timestamp(PREV), "ticker": "AAA", "price": 9.0, "exchange": "N",
         "condition": "M", "t": "x", "fetched_at_utc": "old"},
        {"date": pd.Timestamp(D), "ticker": "AAA", "price": 9.50, "exchange": "N",
         "condition": "M", "t": "x", "fetched_at_utc": "old"},
    ]).to_parquet(cef / co.OFFICIAL_CLOSE_FILE)
    client = FakeClient()
    assert co.collect(make_ctx(env, client)) == co.EXIT_OK
    f = pd.read_parquet(cef / co.OFFICIAL_CLOSE_FILE)
    assert list(f.columns) == list(co.OFFICIAL_CLOSE_COLUMNS)
    assert not f.duplicated(["date", "ticker"]).any()
    assert len(f) == 4                                  # PREV AAA + D AAA, BBB, CCC
    queried = [c[1] for c in client.calls if isinstance(c, tuple) and c[0] == "prints"]
    assert queried == ["BBB", "CCC"], "AAA already had D's print and was queried again"
    assert f.loc[(f.ticker == "AAA") & (f.date == pd.Timestamp(D)), "fetched_at_utc"].item() == "old"


def test_a_later_print_the_client_chose_is_stored_and_flagged_in_the_days_report(env):
    """Two prices from the primary, the later one confirmed by the daily bar (ruling 2026-11-22):
    the price is stored like any other and the day's report names the fund and what was set aside."""
    state, cef = env
    client = FakeClient()
    client.superseded = {"BBB": [{"price": 9.9, "t": "2026-09-29T20:00:00Z"}]}
    assert co.collect(make_ctx(env, client)) == co.EXIT_OK
    f = pd.read_parquet(cef / co.OFFICIAL_CLOSE_FILE)
    assert f.loc[(f.ticker == "BBB") & (f.date == pd.Timestamp(D)), "price"].item() == client.prints["BBB"]
    rep = json.loads((state / "data" / D.isoformat() / "report.json").read_text())
    flags = [x for x in rep["steps"]["official_closes"]["detail"]["flags"]]
    assert flags == [{"fund": "BBB", "check": "two_primary_prints_later_used", "price": client.prints["BBB"],
                      "t": "2026-09-29T20:00:01Z", "superseded": [{"price": 9.9, "t": "2026-09-29T20:00:00Z"}]}]


def test_the_later_print_flag_survives_a_retry_that_does_not_ask_for_that_fund_again(env):
    """Review 2026-11-22: BBB is resolved and stored on the first slot while CCC errors, so the
    step fails; on the next slot BBB is not asked for again. Its flag must still be in the record."""
    client = FakeClient()
    client.superseded = {"BBB": [{"price": 9.9, "t": "2026-09-29T20:00:00Z"}]}
    real = client.closing_auction_prints

    def flaky(symbols, date, **kw):
        if symbols[0] == "CCC":
            raise al.AlpacaHTTPError("GET /v2/stocks/auctions -> HTTP 503", status=503)
        return real(symbols, date, **kw)
    client.closing_auction_prints = flaky
    assert co.collect(make_ctx(env, client)) == co.EXIT_INCOMPLETE
    client.closing_auction_prints = real
    client.calls.clear()
    co.collect(make_ctx(env, client))
    d = status(env)["steps"]["official_closes"]
    assert d["ok"] and ("prints", "BBB") not in client.calls
    assert [(f["fund"], f["check"]) for f in d["detail"]["flags"]] == [("BBB", "two_primary_prints_later_used")]


# ------------------------------------------------------------------ account

def test_account_snapshot_drops_raw_and_credential_like_fields(env):
    state, _ = env
    co.collect(make_ctx(env))
    text = (state / "data" / D.isoformat() / "account.json").read_text()
    assert "SHOULD-NOT-APPEAR" not in text
    acct = json.loads(text)
    assert "raw" not in acct["account"] and acct["account"]["equity"] == 100_500.0
    rows = (state / "equity.csv").read_text().splitlines()
    assert rows[0] == ",".join(co.EQUITY_COLUMNS)
    assert rows[1].startswith(f"{D},100500.0,100000.0,50000.0,80000.0,-29500.0,2,")


def test_account_snapshot_replaces_its_row(env):
    state, _ = env
    (state / "equity.csv").write_text(",".join(co.EQUITY_COLUMNS) + "\n"
                                      f"{PREV},1,1,1,1,1,0,x\n{D},9,9,9,9,9,9,old\n")
    co.collect(make_ctx(env))
    rows = (state / "equity.csv").read_text().splitlines()
    assert len(rows) == 3 and rows[1].startswith(str(PREV)) and "old" not in rows[2]


def test_orders_are_read_from_the_previous_trading_day(env):
    client = FakeClient(now=et(dt.date(2026, 10, 5), 21), next_open=et(dt.date(2026, 10, 6), 9, 30))
    co.collect(make_ctx(env, client, cc_day=dt.date(2026, 10, 5)))
    after = next(c[1] for c in client.calls if isinstance(c, tuple) and c[0] == "orders")
    assert after == et(dt.date(2026, 10, 2), 0)          # Monday's orders went in on Friday


def test_account_is_not_recorded_once_the_next_session_has_opened(env):
    client = FakeClient(now=et(NEXT, 10), is_open=True, next_open=et(dt.date(2026, 10, 1), 9, 30))
    assert co.collect(make_ctx(env, client)) == co.EXIT_INCOMPLETE
    # D is NEXT's previous day here (NEXT's own close is not yet past).
    s = status(env)
    assert not s["steps"]["account_snapshot"]["ok"]
    assert "account" not in client.calls


# ------------------------------------------------------------------ distributions

def test_distributions_need_the_universe_file(env):
    state, cef = env
    (cef / "cef_universe.csv").unlink()
    co.collect(make_ctx(env))
    s = status(env)["steps"]
    assert not s["distributions"]["ok"] and "cef_universe.csv" in s["distributions"]["err"]


# ------------------------------------------------------------------ main / exit codes

def test_unexpected_error_is_recorded_and_exits_20(env, capsys):
    state, _ = env

    class Broken(FakeClient):
        def calendar(self, start, end):
            raise RuntimeError("calendar exploded")

    rc = co.main(["--book", "cef"], env={"QUANTT_STATE_DIR": str(state)},
                 make_ctx=lambda book, sd: make_ctx(env, Broken()))
    assert rc == co.EXIT_UNEXPECTED == 20
    assert log_lines(env) == ["????-??-?? DATA ERROR RuntimeError: calendar exploded"]
    assert "Traceback" in capsys.readouterr().err


def test_unset_state_dir_exits_20():
    assert co.main(["--book", "cef"], env={}, make_ctx=lambda *a: pytest.fail("built")) == 20


def test_a_second_concurrent_run_is_refused(env):
    state, _ = env
    held = co._CollectorLock(state / "data" / ".collect.lock")
    assert held.acquire()
    try:
        rc = co.main(["--book", "cef"], env={"QUANTT_STATE_DIR": str(state)},
                     make_ctx=lambda *a: pytest.fail("a second run built a client"))
    finally:
        held.release()
    assert rc == co.EXIT_INCOMPLETE


# ------------------------------------------------------------------ read-only

def test_collect_package_never_names_the_transmit_method():
    pkg = Path(co.__file__).parent
    for f in pkg.glob("*.py"):
        assert "submit_order" not in f.read_text(), f"{f.name} names submit_order"
    assert not hasattr(FakeClient, "submit_order")


# ------------------------------------------------------------------ borrow snapshot

def _assets(env, day=D):
    import pandas as pd
    return pd.read_parquet(env[0] / "data" / day.isoformat() / co.ASSETS_FILE)


def test_borrow_snapshot_writes_the_whole_list_with_its_read_time(env):
    co.collect(make_ctx(env))
    a = _assets(env)
    assert sorted(a["symbol"]) == ["AAA", "BBB", "ZZZ"] and a["read_at_utc"].notna().all()
    d = status(env)["steps"]["borrow_snapshot"]
    assert d["ok"] and d["detail"]["n_assets"] == 3 and d["detail"]["deployed_not_shortable"] == []
    assert d["detail"]["compared_with"] == "no previous snapshot"


def test_a_deployed_name_whose_borrow_flipped_is_a_flag_and_others_are_not(env):
    import pandas as pd
    prev_dir = env[0] / "data" / PREV.isoformat()
    prev_dir.mkdir(parents=True)
    pd.DataFrame([{"symbol": "AAA", "tradable": True, "shortable": True, "easy_to_borrow": True},
                  {"symbol": "BBB", "tradable": True, "shortable": True, "easy_to_borrow": True},
                  {"symbol": "ZZZ", "tradable": True, "shortable": True, "easy_to_borrow": True}]
                 ).to_parquet(prev_dir / co.ASSETS_FILE)
    client = FakeClient()
    client.flags = {"AAA": (True, False, False), "BBB": (True, True, True), "ZZZ": (True, False, False)}
    assert co.collect(make_ctx(env, client)) == co.EXIT_OK      # report only: never fails the run
    d = status(env)["steps"]["borrow_snapshot"]["detail"]
    got = {(f["fund"], f["field"], f["previous"], f["now"]) for f in d["flags"]}
    assert got == {("AAA", "shortable", True, False), ("AAA", "easy_to_borrow", True, False)}
    assert d["deployed_not_shortable"] == ["AAA"] and d["compared_with"] == PREV.isoformat()


def test_a_deployed_name_missing_from_alpacas_list_is_a_gap(env):
    client = FakeClient()
    client.flags = {"AAA": (True, True, True)}
    co.collect(make_ctx(env, client))
    gaps = status(env)["steps"]["borrow_snapshot"]["detail"]["gaps"]
    assert [g["fund"] for g in gaps] == ["BBB"]


def _borrow_refused(env, client):
    co.collect(make_ctx(env, client))
    s = status(env)["steps"]["borrow_snapshot"]
    return (not s["ok"]) and "assets" not in client.calls


def test_borrow_is_not_read_while_the_market_is_open(env):
    """Only the is_open half of the guard: D's evening date and the right next open."""
    client = FakeClient(now=et(D, 21), is_open=True, next_open=et(NEXT, 9, 30))
    assert _borrow_refused(env, client)


def test_borrow_is_not_read_when_the_next_open_is_not_the_session_after_d(env):
    """Only the next_open half of the guard."""
    client = FakeClient(now=et(D, 21), is_open=False, next_open=et(dt.date(2026, 10, 1), 9, 30))
    assert _borrow_refused(env, client)


def test_borrow_is_not_read_the_next_morning_under_ds_label(env):
    """Market shut and the next open right, but the read would be on D+1's date:
    Alpaca's overnight refresh may be in it. The account snapshot is still fine."""
    client = FakeClient(now=et(NEXT, 8, 30), is_open=False, next_open=et(NEXT, 9, 30))
    assert _borrow_refused(env, client)
    assert status(env)["steps"]["account_snapshot"]["ok"]


def test_the_borrow_guard_judges_its_own_fresh_clock_not_the_runs(env):
    """Review 2026-10-11: this fake's clock never moved, so judging the run's
    start-of-run clock passed every test above. Here the run starts at 23:50 on
    D, and the borrow step's own read lands at 00:05 on D+1: it must refuse."""
    class Late(FakeClient):
        def clock(self):
            c = super().clock()
            return {**c, "timestamp": et(NEXT, 0, 5)} if self.calls.count("clock") > 1 else c
    assert _borrow_refused(env, Late(now=et(D, 23, 50)))


def test_an_empty_asset_list_fails_the_step_so_it_is_retried(env):
    client = FakeClient()
    client.flags = {}
    assert co.collect(make_ctx(env, client)) == co.EXIT_INCOMPLETE
    assert "empty" in status(env)["steps"]["borrow_snapshot"]["err"]


# ------------------------------------------------- eod_equity.csv (team lead, 2026-10-19)
# The official daily P&L series. A CONTRACT read by another branch and a HALVE/KILL
# monitor: header names date, equity, change_usd first. Every equity is synthetic.

import csv  # noqa: E402

OCT5 = dt.date(2026, 10, 5)


def eod_rows(env):
    with open(env[0] / co.EOD_FILE, newline="") as fh:
        rd = csv.DictReader(fh)
        return rd.fieldnames, list(rd)


def eod_step(env, client, day):
    return co.step_eod_equity(make_ctx(env, client), day, client.clock(), {"steps": {}})


def test_eod_file_contract_and_self_backfill_from_the_first_funded_session(env):
    client = FakeClient(now=et(OCT5, 21), next_open=et(dt.date(2026, 10, 6), 9, 30))
    eod_step(env, client, OCT5)
    assert ("eod", dt.date(2026, 9, 28), OCT5) in client.calls     # backfill from the account's start
    header, rows = eod_rows(env)
    assert header[:3] == ["date", "equity", "change_usd"]          # the contract, by name
    assert tuple(header) == co.EOD_COLUMNS
    assert [r["date"] for r in rows] == ["2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01",
                                         "2026-10-02", "2026-10-05"]
    assert rows[0]["change_usd"] == ""                              # first funded session: no baseline
    assert [r["change_usd"] for r in rows[1:]] == ["10.00"] * 5
    assert [float(r["equity"]) for r in rows] == [100_000.0 + 10 * i for i in range(6)]
    assert all(r["read_at_utc"] for r in rows)


def test_eod_first_funded_session_after_the_account_opened_has_an_empty_change(env):
    client = FakeClient()
    client.eod = {D: 100_000.0}            # 2026-09-28 came back as a pre-funding zero, dropped
    eod_step(env, client, D)
    _, rows = eod_rows(env)
    assert [(r["date"], r["change_usd"]) for r in rows] == [("2026-09-29", "")]


def test_eod_step_through_collect_is_ok_and_the_day_idles(env):
    client = FakeClient()
    assert co.collect(make_ctx(env, client)) == co.EXIT_OK
    assert status(env)["steps"]["eod_equity"]["ok"]
    _, rows = eod_rows(env)
    assert [r["date"] for r in rows] == [PREV.isoformat(), D.isoformat()]
    client.calls.clear()
    assert co.collect(make_ctx(env, client)) == co.EXIT_OK
    assert client.calls == ["clock", "calendar"]                    # read once per data day


def test_eod_point_stamped_after_the_run_is_not_written_and_is_retried(env):
    """At 17:10 ET D's point is stamped 20:00 ET: its day has not closed. The day
    stays INCOMPLETE on eod_equity only, and the 20:10 slot writes it."""
    early = FakeClient(now=et(D, 17, 10))
    assert co.collect(make_ctx(env, early)) == co.EXIT_INCOMPLETE
    st = status(env)["steps"]["eod_equity"]
    assert not st["ok"] and "is stamped 2026-09-29T20:00:00-04:00, after this run's clock" in st["err"]
    assert log_lines(env)[-1] == f"{D} DATA INCOMPLETE eod_equity flags=0 gaps=0"
    _, rows = eod_rows(env)
    assert [r["date"] for r in rows] == [PREV.isoformat()]          # earlier days still written
    assert co.collect(make_ctx(env, FakeClient(now=et(D, 20, 10)))) == co.EXIT_OK
    _, rows = eod_rows(env)
    assert [r["date"] for r in rows] == [PREV.isoformat(), D.isoformat()]


def test_eod_no_point_for_d_fails_the_step_and_keeps_the_rest(env):
    client = FakeClient()
    client.eod = {PREV: 100_000.0}
    with pytest.raises(co.StepFailed, match="no point for 2026-09-29 yet"):
        eod_step(env, client, D)
    _, rows = eod_rows(env)
    assert [r["date"] for r in rows] == [PREV.isoformat()]


def test_eod_a_revision_is_written_and_logged_naming_date_old_and_new(env):
    client = FakeClient()
    eod_step(env, client, D)
    _, before = eod_rows(env)
    client = FakeClient(now=et(NEXT, 21), next_open=et(dt.date(2026, 10, 1), 9, 30))
    client.eod = {PREV: 100_000.0, D: 100_015.25, NEXT: 100_020.0}     # D was 100,010.0
    detail = eod_step(env, client, NEXT)
    _, rows = eod_rows(env)
    by = {r["date"]: r for r in rows}
    assert by["2026-09-29"]["equity"] == "100015.25"
    assert (by["2026-09-29"]["change_usd"], by["2026-09-30"]["change_usd"]) == ("15.25", "4.75")
    assert by["2026-09-29"]["read_at_utc"] >= before[1]["read_at_utc"]
    assert log_lines(env) == [f"{NEXT} DATA EOD_REVISED 2026-09-29 equity 100010.0 -> 100015.25 "
                              f"(Alpaca EOD history, read {by['2026-09-29']['read_at_utc']})"]
    (f,) = detail["flags"]
    assert (f["check"], f["date"], f["old"], f["new"]) == ("eod_revised", "2026-09-29",
                                                           "100010.0", "100015.25")


def test_eod_a_missing_session_leaves_change_empty_never_a_two_day_change(env):
    client = FakeClient(now=et(dt.date(2026, 10, 1), 21), next_open=et(dt.date(2026, 10, 2), 9, 30))
    client.eod = {PREV: 100_000.0, NEXT: 100_020.0, dt.date(2026, 10, 1): 100_025.0}   # no 09-29
    detail = eod_step(env, client, dt.date(2026, 10, 1))
    _, rows = eod_rows(env)
    assert [(r["date"], r["change_usd"]) for r in rows] == [
        ("2026-09-28", ""), ("2026-09-30", ""), ("2026-10-01", "5.00")]
    (g,) = detail["gaps"]
    assert g["date"] == "2026-09-30" and "2026-09-29 is not in Alpaca's EOD history" in g["reason"]


def test_eod_a_recorded_day_missing_from_a_later_read_is_kept_and_flagged(env):
    eod_step(env, FakeClient(), D)
    client = FakeClient(now=et(NEXT, 21), next_open=et(dt.date(2026, 10, 1), 9, 30))
    client.eod = {D: 100_010.0, NEXT: 100_020.0}                    # PREV vanished
    detail = eod_step(env, client, NEXT)
    _, rows = eod_rows(env)
    assert [r["date"] for r in rows] == ["2026-09-28", "2026-09-29", "2026-09-30"]
    assert [f["check"] for f in detail["flags"]] == ["eod_absent_from_read"]


def test_eod_a_file_in_another_shape_fails_the_step_and_is_left_alone(env):
    path = env[0] / co.EOD_FILE
    path.write_text("date,equity\n2026-09-28,1\n")
    with pytest.raises(co.StepFailed, match="expected"):
        eod_step(env, FakeClient(), D)
    assert path.read_text() == "date,equity\n2026-09-28,1\n"


def test_the_first_run_after_install_backfills_on_a_day_already_complete(env):
    """On the VM, D's status.json was complete under the old step list. The new
    step is the only one pending, so the next slot runs it alone and writes the
    whole series from 2026-09-28, with no unit or schedule change."""
    client = FakeClient(now=et(OCT5, 21), next_open=et(dt.date(2026, 10, 6), 9, 30))
    old_steps = [s for s in co.STEPS if s != "eod_equity"]
    day_dir = env[0] / "data" / OCT5.isoformat()
    day_dir.mkdir(parents=True)
    (day_dir / "status.json").write_text(json.dumps(
        {"date": OCT5.isoformat(),
         "steps": {s: {"ok": True, "err": None, "detail": {"flags": [], "gaps": []}, "at": "x"}
                   for s in old_steps}}))
    assert co.collect(make_ctx(env, client, cc_day=OCT5)) == co.EXIT_OK
    assert [c for c in client.calls if c not in ("clock", "calendar")] == \
        [("eod", dt.date(2026, 9, 28), OCT5)]
    _, rows = eod_rows(env)
    assert rows[0]["date"] == "2026-09-28" and rows[-1]["date"] == OCT5.isoformat()


def test_eod_an_unparseable_equity_in_the_file_fails_the_step_and_is_left_alone(env):
    """Review 2026-10-19: a hand-edited cell used to reach float() as a bare
    ValueError, which aborts the whole collector run instead of failing one step."""
    path = env[0] / co.EOD_FILE
    text = "date,equity,change_usd,read_at_utc\n2026-09-28,100000.0,,x\n2026-09-29,oops,,x\n"
    path.write_text(text)
    with pytest.raises(co.StepFailed, match="2026-09-29"):
        eod_step(env, FakeClient(now=et(OCT5, 21), next_open=et(dt.date(2026, 10, 6), 9, 30)), OCT5)
    assert path.read_text() == text


def test_an_unexpected_error_in_eod_equity_leaves_every_other_step_done(env):
    """Review 2026-10-19: eod_equity is new code that runs every slot. It runs
    LAST, so a defect in it can never stop the steps that cannot be redone later
    (borrow_snapshot is D's close only) or the ones the book decides on."""
    class Broken(FakeClient):
        def eod_equity_history(self, start, end):
            raise RuntimeError("eod exploded")
    with pytest.raises(RuntimeError, match="eod exploded"):
        co.collect(make_ctx(env, Broken()))
    steps = status(env)["steps"]
    assert all(steps[s]["ok"] for s in co.STEPS if s != "eod_equity"), steps
    assert co.STEPS[-1] == "eod_equity"


# ------------------------------------------------------------------ empty rows (2026-10-28)
# fetch_daily wrote price rows with every price NaN until 2026-10-28 (its
# docstring, EMPTY ROWS: 15 good 2026-09-15 bars on the laptop panel had become
# such rows), and the panel still holds them. A NaN compares False against
# everything, so `_compare` returned None: a deployed name whose panel value for
# D was empty was neither a flag nor a gap. Each of these failed on 4487383.

NAN = float("nan")


def test_an_empty_panel_close_is_a_gap_naming_the_fund_and_date(env):
    state, cef = env
    write_panels(cef, close={"AAA": 9.50, "BBB": NAN})
    assert co.collect(make_ctx(env)) == co.EXIT_OK
    d = status(env)["steps"]["close_crosscheck"]["detail"]
    assert d["flags"] == []
    (g,) = d["gaps"]
    assert g["fund"] == "BBB" and D.isoformat() in g["reason"] and "empty" in g["reason"], g
    assert "cef_prices.parquet" in g["reason"], g


@pytest.mark.parametrize("cc_aaa", [10.02, None], ids=["cefconnect_has_d", "cefconnect_has_no_d"])
def test_an_empty_panel_nav_is_a_gap_naming_the_fund_and_date(env, cc_aaa):
    """Whatever CEFConnect says, an empty panel NAV for D is a gap that says the
    row is empty: never a pass, and never the 'CEFConnect has no NAV' gap, which
    would blame the other source."""
    state, cef = env
    write_panels(cef, nav={"AAA": NAN, "BBB": 20.00})
    assert co.collect(make_ctx(env, cc={"AAA": cc_aaa, "BBB": 20.00})) == co.EXIT_OK
    d = status(env)["steps"]["nav_crosscheck"]["detail"]
    assert d["flags"] == []
    (g,) = d["gaps"]
    assert g["fund"] == "AAA" and D.isoformat() in g["reason"] and "is empty" in g["reason"], g
    assert "cef_nav.parquet" in g["reason"], g


def test_a_cefconnect_nav_that_is_not_finite_is_unreadable_not_agreement(env):
    """The other side of the same comparison: a CEFConnect value that is not
    finite is unreadable, as the session's gate treats it (`nav_gate.read_cc`),
    so the step fails and is retried. It used to compare False and pass."""
    ctx = make_ctx(env, cc={"AAA": NAN, "BBB": 20.00})
    assert co.collect(ctx) == co.EXIT_INCOMPLETE
    d = status(env)["steps"]["nav_crosscheck"]
    assert not d["ok"]
    (e,) = d["detail"]["fetch_errors"]
    assert e.startswith("AAA:") and D.isoformat() in e and "not a finite" in e, e


@pytest.mark.parametrize("a, b", [(NAN, 1.0), (1.0, NAN), (float("inf"), 1.0)])
def test_compare_refuses_a_value_that_is_not_finite(a, b):
    """For the caller that forgets: a value that is not finite raises, naming
    the fund, rather than reading as agreement."""
    with pytest.raises(ValueError, match="AAA.*not finite"):
        co._compare("AAA", "source a", a, "source b", b)


def _fresh_env(root):
    state, cef = root / "state", root / "cef"
    state.mkdir(parents=True)
    cef.mkdir()
    return state, cef


def test_with_no_empty_rows_the_crosschecks_are_unchanged(tmp_path):
    """The no-op proof. (a) A clean panel -- one flag and one missing row in
    each cross-check -- gives exactly the details the pre-fix code gave, pinned
    here and passing on 4487383 too: the same flags, the same gap reasons, the
    same counts. (b) The same day with BBB's rows present but EMPTY instead of
    missing, and a CEFConnect NAV for BBB that would flag if a NaN could be
    compared: the flags are unchanged and BBB is a gap in both checks, its
    reason naming the empty row. Part (b) is what the old code fails."""
    want_nav_flags = [{"fund": "AAA", "source_a": "cef_nav.parquet (yfinance)", "value_a": 10.00,
                       "source_b": "cefconnect", "value_b": 10.02, "diff": -0.02}]
    want_close_flags = [{"fund": "AAA", "source_a": "alpaca official close (M, primary)",
                         "value_a": 9.50, "source_b": "cef_prices.parquet (yfinance)",
                         "value_b": 9.52, "diff": -0.02}]

    a = _fresh_env(tmp_path / "a")
    write_panels(a[1], nav={"AAA": 10.00, "BBB": 20.00}, close={"AAA": 9.52})
    assert co.collect(make_ctx(a, cc={"AAA": 10.02, "BBB": None})) == co.EXIT_OK
    s = status(a)["steps"]
    assert s["nav_crosscheck"]["detail"] == {
        "flags": want_nav_flags,
        "gaps": [{"fund": "BBB", "reason": f"CEFConnect has no NAV dated {D}"}],
        "fetch_errors": []}
    assert s["close_crosscheck"]["detail"] == {
        "flags": want_close_flags,
        "gaps": [{"fund": "BBB", "reason": f"no panel close dated {D}"}]}
    # BBB has no CEFConnect row yet, so the arrival watch is still running.
    assert log_lines(a) == [f"{D} DATA COMPLETE flags=2 gaps=2 watching=cefconnect_arrival"]

    b = _fresh_env(tmp_path / "b")
    write_panels(b[1], nav={"AAA": 10.00, "BBB": NAN}, close={"AAA": 9.52, "BBB": NAN})
    assert co.collect(make_ctx(b, cc={"AAA": 10.02, "BBB": 20.03})) == co.EXIT_OK
    s = status(b)["steps"]
    assert s["nav_crosscheck"]["detail"] == {
        "flags": want_nav_flags,
        "gaps": [{"fund": "BBB", "reason": f"cef_nav.parquet's row dated {D} is empty "
                                           f"(nav nan): no NAV to compare"}],
        "fetch_errors": []}
    assert s["close_crosscheck"]["detail"] == {
        "flags": want_close_flags,
        "gaps": [{"fund": "BBB", "reason": f"cef_prices.parquet's close dated {D} is empty (nan)"}]}
    assert log_lines(b) == [f"{D} DATA COMPLETE flags=2 gaps=2"]


@pytest.mark.parametrize("bad", [NAN, float("inf"), 0.0], ids=["nan", "inf", "zero"])
def test_a_cefconnect_value_that_is_no_nav_is_not_an_arrival(env, bad):
    """Review of the NAV half (2026-10-28): the arrival watch logged any value
    CEFConnect returned as the row's first sighting, NaN included, so the
    arrival time of a real NAV was lost and the file carried a NaN. A value
    that is not a finite positive number (`read_cc`'s test) is now an error,
    read again next slot, and the arrival is logged when a real NAV appears.
    Failed on 377fe41."""
    state, cef = env
    cc = {"AAA": bad, "BBB": 20.00}
    co.collect(make_ctx(env, cc=cc))
    st = status(env)["steps"]["cefconnect_arrival"]
    assert not st["ok"] and "AAA" not in st["detail"]["first_seen"]
    (e,) = st["detail"]["fetch_errors"]
    assert e.startswith("AAA:") and "not recorded as an arrival" in e, e
    rows = pd.read_csv(state / co.ARRIVAL_FILE, keep_default_na=False)
    assert rows["ticker"].tolist() == ["BBB"]
    cc["AAA"] = 10.00                                                # the real row
    co.collect(make_ctx(env, cc=cc))
    rows = pd.read_csv(state / co.ARRIVAL_FILE, keep_default_na=False)
    assert rows["ticker"].tolist() == ["BBB", "AAA"] and rows.iloc[1]["nav"] == 10.0
    assert status(env)["steps"]["cefconnect_arrival"]["ok"]
