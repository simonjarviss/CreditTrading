"""scripts/ops/pnl_report.py: the session and cumulative sections, the gaps it must name, and
that a review-line breach only ever appears in the report.

Fixtures are a small synthetic account: a fake reader (duck-typed like AlpacaReader, every
number invented), fake NAV and dividend sources, and a synthetic price history. The account's
equity series is computed in this file from cash and closes, never from the attribution's
own formulas, so the reconciliation test is a real check. Nothing opens a socket; no key file
is read. Every test fails on the parent commit, where the module does not exist.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import subprocess
import sys
from fractions import Fraction as F
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.cef import exposure_readout as ER
from scripts.cef import live_attribution as LA
from scripts.ops import alpaca_read as AR
from scripts.ops import pnl_report as P

D = dt.date
UTC = dt.timezone.utc
NOW = dt.datetime(2026, 1, 23, 2, 0, tzinfo=UTC)   # after the 01-22 session's 20:00 NY stamp (01:00Z 01-23)
PRE_UNFUNDED = [D(2026, 1, 7), D(2026, 1, 8)]
FUNDED = [D(2026, 1, 12), D(2026, 1, 13), D(2026, 1, 14), D(2026, 1, 15), D(2026, 1, 16)]     # funded, flat
TRADED = [D(2026, 1, 20), D(2026, 1, 21), D(2026, 1, 22)]   # the book trades (01-19 is a holiday)
SESSIONS = FUNDED + TRADED
NEXT = D(2026, 1, 23)
ASOF = TRADED[-1]
CASH0 = 100_000.0
CLOSES = {"AAA": {FUNDED[-1]: "9.90", TRADED[0]: "10.10", TRADED[1]: "10.20", TRADED[2]: "10.05"},
          "BBB": {FUNDED[-1]: "20.10", TRADED[0]: "19.90", TRADED[1]: "20.20", TRADED[2]: "20.40"}}
NAVS = {"AAA": {TRADED[0]: "11.00", TRADED[1]: "11.20", TRADED[2]: "11.00"},
        "BBB": {TRADED[0]: "22.00", TRADED[1]: "22.00", TRADED[2]: "22.40"}}
# (id, symbol, side, qty, px, session)
FILLS = [("f1", "AAA", "buy", 5000, "10.00", TRADED[0]),
         ("f2", "BBB", "sell_short", 2000, "20.00", TRADED[0]),
         ("f3", "AAA", "sell", 1000, "10.15", TRADED[1])]
SIGN = {"buy": 1, "sell": -1, "sell_short": -1}
SEC = F("0.0000206")
CAT = F("0.000003")


def fees_of(rows) -> F:
    sold = sum((F(q) * F(px) for _, _, s, q, px, _ in rows if SIGN[s] < 0), F(0))
    shares = sum((F(q) for _, _, _, q, _, _ in rows), F(0))
    return -(F(math.ceil(SEC * sold * 100), 100) + F(math.ceil(CAT * shares * 100), 100))


def equity_series(tamper=None):
    """Cash + positions at the close - fees, the way the account was measured to behave."""
    cash = F(str(CASH0))
    pos = {"AAA": F(0), "BBB": F(0)}
    out = []
    for d in SESSIONS:
        day = [r for r in FILLS if r[5] == d]
        for fid, s, side, q, px, _ in day:
            pos[s] += SIGN[side] * q
            cash -= SIGN[side] * q * F(px)
        cash += fees_of(day)
        mkt = sum((pos[s] * F(CLOSES[s].get(d, "0")) for s in pos if pos[s] != 0), F(0))
        e = cash + mkt
        out.append((d, float(e) + ((tamper or {}).get(d, 0.0))))
    return out


def stamp(d):
    return dt.datetime.combine(d + dt.timedelta(days=1), dt.time(1, 0), UTC)


class FakeReader:
    def __init__(self, tamper=None, fee_rows=None, fee_error=None):
        self.tamper = tamper
        self.fee_rows = fee_rows
        self.fee_error = fee_error

    def eod_equity_history(self, start, end):
        return [AR.EODPoint(d, e, stamp(d)) for d, e in equity_series(self.tamper) if start <= d <= end]

    def calendar(self, start, end):
        return [{"date": d} for d in PRE_UNFUNDED + SESSIONS + [NEXT] if start <= d <= end]

    def activities_fills(self, date):
        return [{"id": fid, "activity_type": "FILL", "symbol": s, "side": side, "qty": str(q), "price": px,
                 "transaction_time": f"{d.isoformat()}T20:55:00.1Z", "type": "fill", "order_id": fid,
                 "cum_qty": str(q), "leaves_qty": "0", "order_status": "filled"}
                for fid, s, side, q, px, d in FILLS if d == date]

    def distributions(self, symbols, start, end):
        return []

    def corporate_actions(self, symbols, start, end):
        return []

    def fee_activities(self):
        if self.fee_error:
            raise AR.AlpacaHTTPError(self.fee_error, status=500)
        if self.fee_rows is not None:
            return self.fee_rows
        return [{"id": f"fee-{d}", "activity_type": "FEE", "date": d.isoformat(),
                 "net_amount": str(float(fees_of([r for r in FILLS if r[5] == d])))} for d in TRADED]

    def _get(self, base, path, params):
        assert path == "/v2/stocks/bars"
        bars = {s: [{"t": f"{d.isoformat()}T05:00:00Z", "o": float(c), "h": float(c), "l": float(c),
                     "c": float(c), "v": 1000} for d, c in sorted(CLOSES[s].items())]
                for s in params["symbols"].split(",")}
        return {"bars": bars, "next_page_token": None}


def fake_navs(symbols, start, end, drop=None):
    rows = [{"date": d.isoformat(), "ticker": s, "nav": v}
            for s in symbols for d, v in NAVS[s].items() if start <= d <= end and (s, d) != drop]
    return pd.DataFrame(rows, columns=["date", "ticker", "nav"]), []


def fake_dividends(symbols):
    # one old dividend per name: the source "covers" the name; ex-dates are outside the
    # traded window, so distributions resolve only where Alpaca's silence can be a zero.
    return pd.DataFrame([{"ticker": s, "ex_date": "2026-01-02", "amount": "0.05"} for s in symbols],
                        columns=["ticker", "ex_date", "amount"]), []


def price_history(fs, seed=4):
    sess = ER.nyse_sessions(dt.date(2025, 1, 2), ASOF)
    rng = np.random.default_rng(seed)
    n = len(sess)
    z = rng.normal(0, 0.004, size=(n, 4))
    etf = {fs.etfs[0]: z[:, 0], fs.etfs[1]: z[:, 1] + 0.2 * z[:, 0],
           fs.etfs[2]: z[:, 2] + 0.3 * z[:, 1], fs.etfs[3]: z[:, 3] + 0.5 * z[:, 2]}
    rets = pd.DataFrame(etf, index=sess)
    # AAA responds to the headline factor one for one, BBB to a mix, with a small residual
    rets["AAA"] = rets[fs.etfs[-2] if fs.headline == "MUNI" else fs.etfs[0]] + rng.normal(0, 0.0005, n)
    rets["BBB"] = 0.5 * rets[fs.etfs[1]] + rng.normal(0, 0.0005, n)
    rows = []
    for tk in rets.columns:
        close = 40.0 * np.cumprod(1.0 + rets[tk].to_numpy())
        rows.append(pd.DataFrame({"date": sess, "ticker": tk, "close": close, "adj_close": close,
                                  "dividend": 0.0, "split": 0.0}))
    return pd.concat(rows, ignore_index=True)


GROUPS = {"AAA": "muni", "BBB": "hy"}
FAMILIES = {"AAA": "equity_domestic", "BBB": "preferred"}


def run(tmp_path, book="cef", reader=None, navs=fake_navs, price_fetcher="default", monkeypatch=None, groups=None):
    fs = ER.factor_set(book) if book == "cef" else ER.factor_set(book)
    if price_fetcher == "default":
        price_fetcher = lambda t, s, a: (price_history(fs), {}, {})
    return P.run_report(book, tmp_path / book, ASOF, now_utc=NOW, reader=reader or FakeReader(),
                        groups=groups or (GROUPS if book == "cef" else FAMILIES),
                        nav_fetcher=navs, dist_check_fetcher=fake_dividends, price_fetcher=price_fetcher)


def test_the_core_report_has_both_sections_and_derives_the_first_trade(tmp_path):
    rep, code = run(tmp_path)
    assert code == P.EXIT_OK and rep["status"] == "OK"
    att = rep["attribution"]
    assert att["session"]["date"] == ASOF.isoformat()
    assert att["first_trade"] == TRADED[0].isoformat()         # from the fills, never written here
    # the official line is Alpaca's EOD change; the book was flat, so the cumulative from the first
    # trade is the whole history of its equity
    eq = dict(equity_series())
    assert att["session"]["eod_change"] == pytest.approx(eq[TRADED[-1]] - eq[TRADED[-2]])
    cum = att["cumulative"]
    assert cum["eod_change"] == pytest.approx(eq[TRADED[-1]] - CASH0)
    assert cum["sessions"] == len(TRADED) and cum["first_trade"] == TRADED[0].isoformat()
    # the rebuild reconciles to the cent, and hold + fill + fees is what Alpaca showed
    assert att["reconciled"] is True and cum["residual"] == pytest.approx(0.0, abs=1e-9)
    assert cum["hold"] + cum["fill"] + cum["fees"] == pytest.approx(cum["eod_change"], abs=0.005)
    # hold splits into NAV part and discount part (all three sessions carry every NAV except the first)
    assert cum["nav_part"] + cum["disc_part"] == pytest.approx(cum["hold_on_split_sessions"])
    # the report files are where the owner said, with the factor section after the attribution
    out = tmp_path / "cef" / "reports" / "pnl"
    assert (out / f"{ASOF}.json").is_file() and (out / f"{ASOF}.md").is_file()
    md = (out / f"{ASOF}.md").read_text()
    assert md.index("## Attribution") < md.index("## Factor exposure")
    assert json.loads((out / f"{ASOF}.json").read_text())["book"] == "cef"


def test_the_c4_report_uses_its_own_factors_and_family_split(tmp_path, monkeypatch):
    monkeypatch.setattr(ER, "C4_DIMSON_LAGS", 0)
    fs = ER.factor_set("c4")
    rep, code = P.run_report("c4", tmp_path / "c4", ASOF, now_utc=NOW, reader=FakeReader(), groups=FAMILIES,
                             nav_fetcher=fake_navs, dist_check_fetcher=fake_dividends,
                             price_fetcher=lambda t, s, a: (price_history(fs), {}, {}))
    assert code == P.EXIT_OK
    f = rep["factor"]
    assert f["headline"] == "EQUITY" and list(f["factors"]) == ["EQUITY", "TERM", "CREDIT", "PREFERRED"]
    assert f["split"]["kind"] == "by_family" and set(f["split"]["families"]) == {"equity_domestic", "preferred"}
    assert any("TERM (indicative)" in ln for ln in f["lines"])
    assert any("REVIEW_FRACTION" in ln and "vol target 0.06" in ln for ln in f["lines"])


@pytest.mark.parametrize("book", ["cef", "c4"])
def test_the_report_shows_the_line_with_its_three_inputs_and_reads_flags_against_it(tmp_path, book):
    """Ruling A (team lead, 2026-11-10): the line is REVIEW_FRACTION x vol_target_annual x
    sizing_multiplier, each from the book's own spec, and the JSON and the text carry all three
    beside it; every flag is c/target against REVIEW_FRACTION x m. Fails on the parent commit
    (no multiplier, no `review_line`)."""
    rep, _ = run(tmp_path, book=book)
    fs = ER.factor_set(book)
    f = rep["factor"]
    assert f["status"] == "OK"
    rl = f["review_line"]
    assert rl["review_fraction"] == ER.REVIEW_FRACTION and rl["vol_target_annual"] == fs.vol_target
    assert rl["sizing_multiplier"] == fs.sizing_multiplier and rl["multiplier_applied"] == fs.multiplier
    assert rl["value"] == pytest.approx(ER.REVIEW_FRACTION * fs.vol_target * fs.multiplier, rel=1e-15)
    assert rl["of_target"] == pytest.approx(ER.REVIEW_FRACTION * fs.multiplier, rel=1e-15)
    m = "1 (key absent: the unit book)" if fs.sizing_multiplier is None else f"{fs.sizing_multiplier:.4g}"
    assert f["lines"][0].count(f"x vol target {fs.vol_target:.4g} x sizing multiplier {m} = {rl['value']:.4g}") == 1
    for k, x in f["factors"].items():
        assert x["review"] == ("REVIEW" if x["contrib_of_target"] > rl["of_target"] else "within"), k
    on_disk = json.loads((tmp_path / book / "reports" / "pnl" / f"{ASOF}.json").read_text())
    assert on_disk["factor"]["review_line"] == rl


def test_a_review_breach_shows_in_the_report_and_is_report_only(tmp_path):
    rep, _ = run(tmp_path)
    muni = rep["factor"]["factors"]["MUNI"]
    assert muni["review"] == "REVIEW"
    assert any("MUNI (headline)" in ln and "REVIEW" in ln for ln in rep["factor"]["lines"])
    assert not rep.get("notification")
    for ln in rep["factor"]["lines"] + rep["attribution"]["lines"]:
        assert not ln.startswith("ACT"), ln                         # risk_daily's push keys on that prefix
    # the module imports no notifier at any level (docstrings may name it; code cannot)
    import ast
    tree = ast.parse(Path(P.__file__).read_text())
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    froms = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any("report_notify" in m or "ops.halt" in m for m in names | froms)
    called = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
              for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not called & {"notify_act", "_email", "alert"}


def test_a_missing_nav_makes_only_the_split_unmeasured_named(tmp_path):
    rep, code = run(tmp_path, navs=lambda s, st, e: fake_navs(s, st, e, drop=("AAA", TRADED[2])))
    assert code == P.EXIT_OK                  # the 20:30 job can run before the NAV posts: a gap, not a failure
    att = rep["attribution"]
    assert att["session"]["nav_part"] is None and att["session"]["hold"] is not None
    assert att["cumulative"]["unmeasured"]["nav_part"] == [TRADED[2].isoformat()]
    assert att["reconciled"] is True                       # reconciliation does not depend on NAV
    assert any("UNMEASURED" in g and "AAA" in g for g in rep["gaps"])
    assert any("NAV part over sessions with every NAV" in ln and "UNMEASURED on 1" in ln for ln in att["lines"])
    assert rep["status"] == "OK"                           # the attribution still reconciles


def test_the_nav_source_the_job_builds_uses_each_books_own_symbols(monkeypatch):
    """The job's default NAV source goes through the book's symbols; on the parent commit it
    asked the core's X rule for C4 too, and 15 funds' split was UNMEASURED for ever."""
    asked = []

    class YF:
        def Ticker(self, s):
            asked.append(s)
            return self

        def history(self, **kw):
            return pd.DataFrame({"Close": []})

    monkeypatch.setitem(sys.modules, "yfinance", YF())
    P.safe_nav_fetcher([], "c4")(["ADX"], D(2026, 11, 2), D(2026, 11, 3))
    P.safe_nav_fetcher([], "cef")(["PDI"], D(2026, 11, 2), D(2026, 11, 3))
    assert asked == ["XADEX", "XPDIX"]


def test_an_unknown_name_costs_only_its_nav_named(monkeypatch):
    """A C4 name outside the map: the NAV source fails, named, and the split is UNMEASURED."""
    monkeypatch.setitem(sys.modules, "yfinance", object())
    gaps: list = []
    rows, empty = P.safe_nav_fetcher(gaps, "c4")(["ZZZZ"], D(2026, 11, 2), D(2026, 11, 3))
    assert rows.empty and empty == ["ZZZZ"]
    assert len(gaps) == 1 and "ZZZZ" in gaps[0] and "c4" in gaps[0]


def test_an_unreconciled_session_is_said_loudly(tmp_path, capsys):
    """The ruling is "else say so loudly": the overall status, in the report's headline and
    on the job's stdout line, not only in a body line. Fails on the parent commit, whose
    overall status was OK. The exit code is EXIT_UNRECONCILED since the team lead's ruling of
    2026-11-10 (it was 0; module docstring, EXIT CODES)."""
    rep, code = run(tmp_path, reader=FakeReader(tamper={TRADED[1]: 5.0}))
    att = rep["attribution"]
    assert att["reconciled"] is False and code == P.EXIT_UNRECONCILED
    assert any(ln.startswith("RECONCILIATION FAILED") and TRADED[1].isoformat() in ln for ln in att["lines"])
    assert rep["status"] == P.UNRECONCILED
    md = (tmp_path / "cef" / "reports" / "pnl" / f"{ASOF}.md").read_text()
    assert "RECONCILIATION FAILED" in md
    assert "Overall: **UNRECONCILED**" in md and md.index("**RECONCILIATION FAILED") < md.index("## Attribution")
    assert "UNRECONCILED" in capsys.readouterr().out


def test_an_unreconciled_report_is_written_then_the_unit_exits_non_zero(tmp_path, capsys):
    """Ruling B (team lead, 2026-11-10): an UNRECONCILED report exits EXIT_UNRECONCILED, a code
    of its own, and only after both report files exist; risk_daily, on its own timer, then
    reads that same JSON and shows its WATCH, as before. Fails on the parent commit (exit 0)."""
    rep, code = run(tmp_path, reader=FakeReader(tamper={TRADED[1]: 5.0}))
    assert code == P.EXIT_UNRECONCILED
    assert code not in (P.EXIT_OK, P.EXIT_REFUSED, P.EXIT_INCOMPLETE, 1)
    out = tmp_path / "cef" / "reports" / "pnl"
    on_disk = json.loads((out / f"{ASOF}.json").read_text())
    assert on_disk["status"] == P.UNRECONCILED and on_disk["attribution"]["reconciled"] is False
    assert "Overall: **UNRECONCILED**" in (out / f"{ASOF}.md").read_text()
    assert f"UNRECONCILED; exit {P.EXIT_UNRECONCILED}" in capsys.readouterr().out
    from scripts.ops import risk_daily as RD
    a = RD.attribution_block("cef", tmp_path / "cef", ASOF)
    assert a["status"] == RD.WATCH and a["data"]["reconciled"] is False
    assert any(ln.startswith("RECONCILIATION FAILED") and TRADED[1].isoformat() in ln for ln in a["lines"])


def test_a_reconciled_report_exits_zero_even_with_a_factor_gap(tmp_path):
    """Pin (passes before and after ruling B): reconciled is 0, and a factor block that could
    not be measured costs only that block, never the exit code."""
    rep, code = run(tmp_path)
    assert code == P.EXIT_OK == 0 and rep["attribution"]["reconciled"] is True

    def broken(tickers, start, asof):
        return pd.DataFrame(), {}, {"AAA": "x", "BBB": "y"}
    rep, code = run(tmp_path, price_fetcher=broken)
    assert code == P.EXIT_OK and rep["factor"]["status"] == P.UNMEASURED and rep["status"] == "PARTIAL"


def test_an_incomplete_run_exits_4_even_when_the_account_would_not_reconcile(tmp_path):
    """Ruling B's precedence: incomplete (4) outranks unreconciled (5), because with no fills
    read nothing was reconciled. The account below would not reconcile (its equity is
    tampered), but its fills cannot be read. End to end this is a pin (the parent exits 4 as
    well); the table test below fails on the parent."""
    class DeadFills(FakeReader):
        def activities_fills(self, date):
            raise AR.AlpacaHTTPError("GET /v2/account/activities/FILL failed after 5 attempts", status=500)
    rep, code = run(tmp_path, reader=DeadFills(tamper={TRADED[1]: 5.0}))
    assert code == P.EXIT_INCOMPLETE and rep["status"] == P.UNMEASURED
    assert rep["attribution"]["reconciled"] is None and "AlpacaHTTPError" in rep["attribution"]["why"]
    assert (tmp_path / "cef" / "reports" / "pnl" / f"{ASOF}.json").is_file()


def test_the_exit_code_table():
    """The module docstring's EXIT CODES, as a function (team lead, 2026-11-10). Fails on the
    parent commit (no `exit_code`, no EXIT_UNRECONCILED)."""
    assert P.exit_code(incomplete=False, reconciled=True) == P.EXIT_OK == 0
    assert P.exit_code(incomplete=False, reconciled=False) == P.EXIT_UNRECONCILED == 5
    assert P.exit_code(incomplete=True, reconciled=None) == P.EXIT_INCOMPLETE == 4
    assert P.exit_code(incomplete=True, reconciled=False) == P.EXIT_INCOMPLETE          # 4 wins
    assert P.exit_code(incomplete=True, reconciled=True) == P.EXIT_INCOMPLETE
    with pytest.raises(ValueError, match="not True or False"):
        P.exit_code(incomplete=False, reconciled=None)                                # never a quiet 0
    assert len({P.EXIT_OK, P.EXIT_REFUSED, P.EXIT_INCOMPLETE, P.EXIT_UNRECONCILED, 1}) == 5   # 1: a crash


def test_a_reconciled_report_is_not_called_unreconciled_when_the_factor_block_is_missing(tmp_path):
    """Pin: PARTIAL stays what it was. Only a failed reconciliation is UNRECONCILED, and it
    outranks a missing factor block."""
    def broken(tickers, start, asof):
        return pd.DataFrame(), {}, {"AAA": "x", "BBB": "y"}
    rep, _ = run(tmp_path, price_fetcher=broken)
    assert rep["status"] == "PARTIAL"
    rep, _ = run(tmp_path, reader=FakeReader(tamper={TRADED[1]: 5.0}), price_fetcher=broken)
    assert rep["status"] == P.UNRECONCILED


def test_missing_keys_mark_the_unit_failed_and_the_report_names_them(tmp_path, monkeypatch):
    for k in ("ALPACA_CEF_KEY_ID", "ALPACA_CEF_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    rep, code = P.run_report("cef", tmp_path / "cef", ASOF, now_utc=NOW, groups=GROUPS,
                             nav_fetcher=fake_navs, dist_check_fetcher=fake_dividends)
    assert code == P.EXIT_INCOMPLETE
    assert rep["status"] == P.UNMEASURED and "ALPACA_CEF_KEY_ID" in rep["attribution"]["why"]
    assert (tmp_path / "cef" / "reports" / "pnl" / f"{ASOF}.md").is_file()
    assert "the attribution did not run" in rep["factor"]["why"]


def test_a_broker_read_failure_marks_the_unit_failed(tmp_path):
    class Dead(FakeReader):
        def eod_equity_history(self, start, end):
            raise AR.AlpacaHTTPError("GET x failed after 5 attempts", status=500)
    rep, code = run(tmp_path, reader=Dead())
    assert code == P.EXIT_INCOMPLETE and rep["status"] == P.UNMEASURED and "AlpacaHTTPError" in rep["attribution"]["why"]


def test_yfinance_failure_for_a_held_name_costs_only_the_factor_block(tmp_path):
    """Since ruling C (team lead, 2026-11-10) a held name with no price history is left out and
    named, and the block is PARTIAL, not UNMEASURED; the attribution is untouched."""
    def broken(tickers, start, asof):
        fs = ER.factor_set("cef")
        px = price_history(fs)
        return px[px["ticker"] != "BBB"], {}, {"BBB": "ReadoutError: yfinance returned no rows for BBB"}
    rep, code = run(tmp_path, price_fetcher=broken)
    assert code == P.EXIT_OK and rep["status"] == "PARTIAL"
    assert rep["factor"]["status"] == "PARTIAL" and [m["symbol"] for m in rep["factor"]["missing"]] == ["BBB"]
    assert "no price history in the fetch (ReadoutError: yfinance returned no rows for BBB)" == \
        rep["factor"]["missing"][0]["reason"]
    assert rep["attribution"]["status"] == "OK"


def _late(drop):
    """A price fetch whose rows for the tickers in `drop` stop a session before the as-of: a
    late same-day price (HYT's, CLAUDE.md landmine 6)."""
    def fetch(tickers, start, asof):
        px = price_history(ER.factor_set("cef"))
        return px[~(px["ticker"].isin(drop) & (px["date"] == pd.Timestamp(ASOF)))].reset_index(drop=True), {}, {}
    return fetch


def _positions_at_closes():
    """The fixture account's shares at each traded close, from its fills, and Alpaca's close."""
    q, rows = {"AAA": 0, "BBB": 0}, []
    for d in TRADED:
        for _, s, side, n, _, dd in FILLS:
            if dd == d:
                q[s] += SIGN[side] * n
        rows.append({s: q[s] for s in q})
    return rows


def test_a_late_same_day_price_makes_the_factor_block_partial_not_unmeasured(tmp_path):
    """Ruling C (team lead, 2026-11-10): BBB has no price at the as-of close. The block is
    PARTIAL; it names BBB, its reason and its share of the book's gross at the attribution's
    closes (computed here from the fixture's own shares and closes); the exposures at that
    close equal a direct strict readout of the same prices with BBB not held that day; every
    flag there says PARTIAL; and risk_daily reads the block as a WATCH naming the share. Fails
    on the parent commit, where the block was UNMEASURED."""
    rep, code = run(tmp_path, price_fetcher=_late({"BBB"}))
    f = rep["factor"]
    assert code == P.EXIT_OK and rep["status"] == "PARTIAL" and rep["attribution"]["reconciled"] is True
    assert f["status"] == "PARTIAL" and [m["symbol"] for m in f["missing"]] == ["BBB"]
    assert f["missing"][0]["reason"] == f"no close on {ASOF} (its price history ends {TRADED[-2]})"
    q = _positions_at_closes()[-1]
    gross = {s: abs(q[s] * F(CLOSES[s][ASOF])) for s in q}
    assert f["missing"][0]["shares"] == q["BBB"] and f["missing"][0]["gross_usd"] == pytest.approx(float(gross["BBB"]))
    assert f["missing_gross_share"] == pytest.approx(float(gross["BBB"] / (gross["AAA"] + gross["BBB"])), rel=1e-12)
    assert f["partial_dates"] == {ASOF.isoformat(): ["BBB"]}
    # the exposures at the close: a strict readout of the same prices, BBB not held on the as-of
    fs = ER.factor_set("cef")
    px = _late({"BBB"})(None, None, None)[0]
    eq = dict(equity_series())
    rows = [dict(date=d.isoformat(), symbol=s, shares=float(n), equity=eq[d])
            for d, qq in zip(TRADED, _positions_at_closes()) for s, n in qq.items() if n and not (d == ASOF and s == "BBB")]
    direct = ER.readout(px, pd.DataFrame(rows), GROUPS, fs=fs).exposure
    direct = direct[direct["date"] == pd.Timestamp(ASOF)].set_index("factor")
    for k, x in f["factors"].items():
        assert x["exposure_usd"] == pytest.approx(float(direct.at[k, "exposure_usd"]), rel=1e-12), k
        assert x["review"] == f"{direct.at[k, 'review']} (PARTIAL)", k
    assert f["lines"][0].startswith("Factor exposure PARTIAL") and "BBB" in f["lines"][0]
    assert f"{f['missing_gross_share']:.1%} of the book's gross" in f["lines"][0]
    assert all("(PARTIAL)" in ln for ln in f["lines"] if ln.startswith(("MUNI (", "TERM (", "CREDIT (", "LOANS (")))
    md = (tmp_path / "cef" / "reports" / "pnl" / f"{ASOF}.md").read_text()
    assert "## Factor exposure against the review line (PARTIAL)" in md
    from scripts.ops import risk_daily as RD
    b = RD.factor_block("cef", tmp_path / "cef", ASOF)
    assert b["status"] == RD.WATCH and b["data"]["missing"] == ["BBB"]
    assert b["lines"][0].startswith("Factor exposure PARTIAL: BBB left out") and \
        f"{f['missing_gross_share']:.1%} of the book's gross" in b["lines"][0]


def test_every_held_name_late_or_a_factor_etf_late_stays_unmeasured(tmp_path):
    """Ruling C's edges: no held name with its inputs, or a factor ETF without its price, leaves
    the block UNMEASURED, as before, naming why. A pin on the outcome (the parent was
    UNMEASURED for the first case too, for another reason); the ETF case fails on the parent,
    whose readout raised instead of naming the ETF."""
    rep, code = run(tmp_path, price_fetcher=_late({"AAA", "BBB"}))
    assert code == P.EXIT_OK and rep["factor"]["status"] == P.UNMEASURED
    assert f"no held name has every input the readout needs on {ASOF}" in rep["factor"]["why"]
    etf = ER.factor_set("cef").etfs[0]
    rep, code = run(tmp_path, price_fetcher=_late({etf}))
    assert code == P.EXIT_OK and rep["factor"]["status"] == P.UNMEASURED
    assert rep["factor"]["why"].startswith(f"factor ETF price unavailable at the close of {ASOF}: {etf}")


# --- a flat close and an earlier-only exclusion (independent review of PR #82, 2026-11-11) ---

THIS = sys.modules[__name__]
FLATTEN = [("f4", "AAA", "sell", 4000, "10.05", TRADED[2]),     # the whole book closed at the as-of close
           ("f5", "BBB", "buy", 2000, "20.40", TRADED[2])]
COVER_BBB_EARLY = [("f4", "BBB", "buy", 2000, "20.20", TRADED[1])]   # BBB held at the 01-20 close only


def _unserved(sym, book="cef"):
    """A price fetch that never serves `sym` (a fund yfinance no longer serves: merged, renamed)."""
    def fetch(tickers, start, asof):
        px = price_history(ER.factor_set(book))
        return px[px["ticker"] != sym].reset_index(drop=True), {}, {sym: f"ReadoutError: yfinance returned no rows for {sym}"}
    return fetch


def _assert_flat_block(f, md_path, book):
    """A FLAT block reads nothing for the as-of close and shows no earlier close as it."""
    assert f["lines"][0].startswith(f"Factor exposure at the close of {ASOF}: FLAT, the book holds no position"), \
        f["lines"][0]
    assert f["status"] == "FLAT" == P.FLAT and f["flat"] is True and f["asof"] == ASOF.isoformat()
    assert not {"factors", "split", "gross_usd", "net_usd", "missing", "missing_gross_share"} & set(f)
    for ln in f["lines"]:
        assert f"at the close of {TRADED[1]}" not in ln, ln            # never the previous close's reading
        assert "(PARTIAL)" not in ln and ": within" not in ln and ": REVIEW" not in ln, ln
        assert not ln.startswith(tuple(f"{k} (" for k in [f.get("headline")] + list(ER.factor_set(book).indicative))), ln
    md = md_path.read_text()
    assert "Overall: **OK**." in md and "## Factor exposure against the review line (FLAT)" in md


def _account_record(state, day, qty):
    """The collector's account record for `day` as `quantt/collect/collect.py`'s account_snapshot
    writes it (the fields risk_daily's FLAT cross-check reads), `qty` {symbol: signed shares}."""
    d = state / "data" / day.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    (d / "account.json").write_text(json.dumps({"date": day.isoformat(), "read_at_utc": f"{day.isoformat()}T22:10:05+00:00",
                                                "positions": {"qty": qty, "raw": []}}))


@pytest.mark.parametrize("book", ["cef", "c4"])
def test_a_book_flat_at_the_as_of_close_is_flat_never_the_previous_close(tmp_path, monkeypatch, book):
    """Finding 2 of the independent review of PR #82 (2026-11-11). The account sells everything
    at the 01-22 close. The block says FLAT for 01-22 and prints no exposure, flag or PARTIAL for
    it; its history covers 01-20..01-21, labelled with those dates; the report is OK and
    risk_daily shows INFO, the collector's account record for 01-22 holding nothing either
    (its cross-check: team lead, 2026-11-11). Fails on the parent commit, where the block was
    OK and read at the close of 01-21 ("MUNI ... REVIEW" for a book holding nothing)."""
    monkeypatch.setattr(THIS, "FILLS", FILLS + FLATTEN)
    rep, code = run(tmp_path, book=book)
    f = rep["factor"]
    assert code == P.EXIT_OK and rep["status"] == "OK" and rep["attribution"]["reconciled"] is True
    _assert_flat_block(f, tmp_path / book / "reports" / "pnl" / f"{ASOF}.md", book)
    assert f["history_dates"] == [TRADED[0].isoformat(), TRADED[1].isoformat()]
    assert f["lines"][1].startswith(f"History since the first trade ({TRADED[0]}), each date read at its own close: "
                                    f"2 earlier close(s) with a position, {TRADED[0]} to {TRADED[1]}")
    assert set(f["history"]) == {f["headline"], *ER.factor_set(book).indicative}
    assert all(h["dates"] == 2 for h in f["history"].values())
    assert "earlier_exclusions" not in f and not any(ln.startswith("History note") for ln in f["lines"])
    from scripts.ops import risk_daily as RD
    _account_record(tmp_path / book, ASOF, {})
    b = RD.factor_block(book, tmp_path / book, ASOF)
    assert b["status"] == RD.INFO and b["lines"][1:] == f["lines"]
    assert b["lines"][0].startswith(f"Factor exposure FLAT at the close of {ASOF}, cross-checked")


def test_a_flat_close_after_a_name_left_out_earlier_never_raises(tmp_path, monkeypatch):
    """Finding 1 of the independent review of PR #82 (2026-11-11): the same flat account with BBB
    never served by the price fetch, so BBB is left out on 01-20 and 01-21. The block is FLAT,
    and its history names BBB on both dates in a note that raises no severity. Fails on the
    parent commit, where the PARTIAL share was read against the 01-22 gross, 0, and the block
    said "UNMEASURED: ReadoutError: the attribution's gross at the close of 2026-01-22 is 0"."""
    monkeypatch.setattr(THIS, "FILLS", FILLS + FLATTEN)
    rep, code = run(tmp_path, price_fetcher=_unserved("BBB"))
    f = rep["factor"]
    assert f["status"] != P.UNMEASURED, f["why"]
    assert code == P.EXIT_OK and rep["status"] == "OK"
    _assert_flat_block(f, tmp_path / "cef" / "reports" / "pnl" / f"{ASOF}.md", "cef")
    assert f["partial_dates"] == {TRADED[0].isoformat(): ["BBB"], TRADED[1].isoformat(): ["BBB"]}
    assert [(x["date"], x["symbol"]) for x in f["earlier_exclusions"]] == [(TRADED[0].isoformat(), "BBB"),
                                                                          (TRADED[1].isoformat(), "BBB")]
    note = [ln for ln in f["lines"] if ln.startswith("History note")]
    assert len(note) == 1 and f"no severity: the book holds nothing at the close of {ASOF}" in note[0]
    assert f"{TRADED[0]} BBB (no price history in the fetch (ReadoutError: yfinance returned no rows for BBB))" in note[0]
    from scripts.ops import risk_daily as RD
    _account_record(tmp_path / "cef", ASOF, {})
    assert RD.factor_block("cef", tmp_path / "cef", ASOF)["status"] == RD.INFO


def test_a_flat_close_whose_history_cannot_be_read_stays_flat_naming_the_gap(tmp_path, monkeypatch):
    """The as-of reading of a flat book needs no price, so a history that cannot be read (here no
    held name has its inputs on any earlier date) is UNMEASURED in its own line, named, and the
    block stays FLAT. Fails on the parent commit (no FLAT block)."""
    monkeypatch.setattr(THIS, "FILLS", FILLS + FLATTEN)

    def none_served(tickers, start, asof):
        px = price_history(ER.factor_set("cef"))
        return px[~px["ticker"].isin(["AAA", "BBB"])].reset_index(drop=True), {}, {"AAA": "gone", "BBB": "gone"}
    rep, code = run(tmp_path, price_fetcher=none_served)
    f = rep["factor"]
    assert f["status"] == "FLAT", f.get("why")
    assert code == P.EXIT_OK and rep["status"] == "OK" and f["status"] == P.FLAT and f["history"] is None
    assert f["lines"][1].startswith(f"History since the first trade ({TRADED[0]}) UNMEASURED: no held name has every input")
    assert "AAA (gone)" in f["history_why"]


@pytest.mark.parametrize("exc", [TypeError("simulated bug in the readout"),
                                 ER.LookaheadError("simulated: a beta window date is not strictly before t")],
                         ids=["bug", "lookahead"])
def test_a_bug_or_a_lookahead_in_a_flat_books_history_ends_as_on_a_held_night(tmp_path, monkeypatch, exc):
    """Second review of PR #82 (2026-11-11), its regression finding: `_factor_flat` caught every
    exception from the history read, so on a flat night a TypeError (a bug) or exposure_readout's
    LookaheadError (the runtime H7 assertion) was a history line under a FLAT block, the report
    OK and risk_daily INFO, while on a held night the same failure is UNMEASURED, PARTIAL and
    UNMEASURED. Both nights now end the same way. Fails on the parent d8e9c06, where the flat
    night read FLAT / OK / INFO."""
    from scripts.ops import risk_daily as RD

    def raises(*a, **k):
        raise exc
    monkeypatch.setattr(ER, "readout", raises)
    held, held_code = run(tmp_path / "held")
    monkeypatch.setattr(THIS, "FILLS", FILLS + FLATTEN)
    flat, flat_code = run(tmp_path / "flat")
    for night, rep, code in (("held", held, held_code), ("flat", flat, flat_code)):
        f = rep["factor"]
        assert f["status"] == P.UNMEASURED, (night, f["status"], f["lines"])
        assert f["lines"] == [f"Factor exposure UNMEASURED: {type(exc).__name__}: {exc}"], night
        assert rep["status"] == "PARTIAL" and code == P.EXIT_OK and rep["attribution"]["reconciled"] is True, night
        assert RD.factor_block("cef", tmp_path / night / "cef", ASOF)["status"] == RD.UNMEASURED, night


class _PhantomReader(FakeReader):
    """The second review of PR #82's false FLAT (2026-11-11): the activities list closing fills
    the account never made, while its equity series (and its FEE rows) come from the real fills
    only, so the account still holds AAA +4000 and BBB -2000 at the 01-22 close."""
    def __init__(self, extra):
        super().__init__()
        self.extra = extra

    def activities_fills(self, date):
        return super().activities_fills(date) + [
            {"id": fid, "activity_type": "FILL", "symbol": s, "side": side, "qty": str(q), "price": px,
             "transaction_time": f"{d.isoformat()}T20:55:00.1Z", "type": "fill", "order_id": fid,
             "cum_qty": str(q), "leaves_qty": "0", "order_status": "filled"}
            for fid, s, side, q, px, d in self.extra if d == date]


# A sale price whose fill P&L cancels the phantom fills' modelled fees to the cent, so the rebuild
# reconciles although its positions are wrong (the review's contrived variant).
PHANTOM_RECONCILING = [("f4", "AAA", "sell", 4000, "10.0502125", TRADED[2]), ("f5", "BBB", "buy", 2000, "20.40", TRADED[2])]


def test_a_phantom_closing_fill_never_makes_the_block_flat(tmp_path):
    """Team lead, 2026-11-11 (second review of PR #82): FLAT is never read from a rebuild that
    does not reconcile. A closing fill the account never made flattens the rebuild, and the
    rebuild misses the official change on 01-22; the block is UNMEASURED, saying whether the book
    is flat cannot be read from it, and risk_daily shows UNMEASURED. Fails on the parent d498c4f,
    where the block was FLAT and risk_daily INFO while the account held two positions."""
    from scripts.ops import risk_daily as RD
    rep, code = run(tmp_path, reader=_PhantomReader(FLATTEN))
    f = rep["factor"]
    assert rep["attribution"]["reconciled"] is False and rep["status"] == P.UNRECONCILED and code == P.EXIT_UNRECONCILED
    assert f["status"] == P.UNMEASURED, f["lines"]
    assert f["lines"] == [f"Factor exposure UNMEASURED: {f['why']}"]
    assert f["why"].startswith(f"the fill rebuild holds no position at the close of {ASOF}, but it does not reconcile")
    assert "whether the book is flat at that close cannot be read from it" in f["why"]
    assert "flat" not in f and not any("FLAT, the book holds no position" in ln for ln in f["lines"])
    _account_record(tmp_path / "cef", ASOF, {"AAA": 4000, "BBB": -2000})
    assert RD.factor_block("cef", tmp_path / "cef", ASOF)["status"] == RD.UNMEASURED


def test_a_phantom_fill_that_reconciles_is_caught_by_risk_dailys_cross_check(tmp_path):
    """Team lead, 2026-11-11 (second review of PR #82): the contrived phantom whose P&L cancels
    its modelled fees reconciles, so the job, which reads FLAT from its rebuild, still says FLAT;
    risk_daily's cross-check against the collector's account record for 01-22 says WATCH when
    that record holds the two positions, naming the counts and symbols, and UNMEASURED when there
    is no record, never INFO. Fails on the parent d498c4f, where risk_daily read INFO."""
    from scripts.ops import risk_daily as RD
    rep, code = run(tmp_path, reader=_PhantomReader(PHANTOM_RECONCILING))
    assert rep["attribution"]["reconciled"] is True and rep["status"] == "OK" and code == P.EXIT_OK
    assert rep["factor"]["status"] == P.FLAT                 # the rebuild alone cannot see it
    state = tmp_path / "cef"
    b = RD.factor_block("cef", state, ASOF)
    assert b["status"] == RD.UNMEASURED, b["lines"][0]
    assert b["lines"][0].startswith(f"Factor exposure FLAT at the close of {ASOF} not cross-checked (UNMEASURED): "
                                    f"no account record at {state / 'data' / ASOF.isoformat() / 'account.json'}")
    _account_record(state, ASOF, {"AAA": 4000, "BBB": -2000})
    b = RD.factor_block("cef", state, ASOF)
    assert b["status"] == RD.WATCH, b["lines"][0]
    assert b["lines"][0].startswith(f"Factor exposure FLAT DISAGREES with the account at the close of {ASOF} (WATCH)")
    assert "shows 2 position(s), 1 long and 1 short (AAA, BBB)" in b["lines"][0] and "4000" not in b["lines"][0]
    assert b["lines"][1:] == rep["factor"]["lines"] and not any(ln.startswith("ACT") for ln in b["lines"])
    assert b["data"]["flat_cross_check"]["positions"] == 2


def test_a_name_left_out_only_on_an_earlier_date_is_a_history_note_not_partial(tmp_path, monkeypatch):
    """Finding 3 of the independent review of PR #82 (2026-11-11). BBB is covered at the 01-21
    close and never served by the price fetch (a merged or renamed fund), so it is left out on
    01-20 only; at the 01-22 close the book holds AAA, which is read. The block is OK, not
    PARTIAL: its exposures at the close equal a strict readout of the same book (BBB left out of
    01-20, the date it was excluded on), no flag says PARTIAL, and the 01-20 exclusion is a named
    history note; risk_daily shows INFO. Fails on the parent commit, where the block was PARTIAL
    and risk_daily a WATCH, every night from then on."""
    monkeypatch.setattr(THIS, "FILLS", FILLS + COVER_BBB_EARLY)
    rep, code = run(tmp_path, price_fetcher=_unserved("BBB"))
    f = rep["factor"]
    assert f["status"] == "OK", f["lines"][0]
    assert code == P.EXIT_OK and rep["status"] == "OK"
    assert "missing" not in f and "missing_gross_share" not in f
    assert f["partial_dates"] == {TRADED[0].isoformat(): ["BBB"]}
    assert [(x["date"], x["symbol"], x["shares"]) for x in f["earlier_exclusions"]] == [(TRADED[0].isoformat(), "BBB", -2000.0)]
    assert f["lines"][0].startswith(f"Factor exposure at the close of {ASOF} (headline MUNI")
    assert not any("(PARTIAL)" in ln for ln in f["lines"])
    assert all(x["review"] in ("REVIEW", "within") for x in f["factors"].values())
    note = [ln for ln in f["lines"] if ln.startswith("History note")]
    assert len(note) == 1 and f"no severity: every name held at the close of {ASOF} is read" in note[0]
    assert f"{TRADED[0]} BBB (no price history in the fetch (ReadoutError: yfinance returned no rows for BBB))" in note[0]
    # the as-of reading is the strict readout of what was held, BBB left out of its one date
    px = _unserved("BBB")(None, None, None)[0]
    eq = dict(equity_series())
    q = {"AAA": 0, "BBB": 0}
    rows = []
    for d in TRADED:
        for _, s, side, n, _, dd in FILLS + COVER_BBB_EARLY:
            if dd == d:
                q[s] += SIGN[side] * n
        rows += [dict(date=d.isoformat(), symbol=s, shares=float(n), equity=eq[d]) for s, n in q.items() if n and s != "BBB"]
    direct = ER.readout(px, pd.DataFrame(rows), GROUPS, fs=ER.factor_set("cef")).exposure
    direct = direct[direct["date"] == pd.Timestamp(ASOF)].set_index("factor")
    for k, x in f["factors"].items():
        assert x["exposure_usd"] == pytest.approx(float(direct.at[k, "exposure_usd"]), rel=1e-12), k
        assert x["review"] == direct.at[k, "review"], k
    from scripts.ops import risk_daily as RD
    b = RD.factor_block("cef", tmp_path / "cef", ASOF)
    assert b["status"] == RD.INFO and b["lines"] == f["lines"]


# held 01-20, flat 01-21, held again 01-22 (the 01-20 book is the plain fixture's): the review's interlude
INTERLUDE = [("f1", "AAA", "buy", 5000, "10.00", TRADED[0]), ("f2", "BBB", "sell_short", 2000, "20.00", TRADED[0]),
             ("f3", "AAA", "sell", 5000, "10.20", TRADED[1]), ("f4", "BBB", "buy", 2000, "20.20", TRADED[1]),
             ("f5", "AAA", "buy", 4000, "10.05", TRADED[2]), ("f6", "BBB", "sell_short", 2000, "20.40", TRADED[2])]


def _cum_lines(f):
    return [ln for ln in f["lines"] if ln.startswith("Cumulative factor P&L")]


def test_every_cumulative_factor_pnl_line_labels_the_sessions_it_covers(tmp_path, monkeypatch):
    """Second review of PR #82 (2026-11-11): the cumulative factor P&L leaves out a session that
    closed flat after a held close (the team lead left that to a follow-up PR), so each line that
    prints it says which sessions it covers: the count, the first and last, and the rule (the
    sums are the readout's own, not changed). Held through 01-22: 01-21 and 01-22. Flat at
    01-22: 01-21 only. Fails on
    the parent 51b209f, whose held line named no session and whose flat line only the last."""
    rule = ("each a session whose previous close and own close both held a position; a session that closed flat "
            "after a held close is not in it (not read here: a follow-up PR, team lead, 2026-11-11)")
    rep, _ = run(tmp_path / "held")
    f = rep["factor"]
    assert f["status"] == "OK" and len(_cum_lines(f)) == 1
    assert _cum_lines(f)[0].startswith(f"Cumulative factor P&L (book, E(t-1) x f(t), model reading) over 2 session(s), "
                                       f"{TRADED[1]} to {TRADED[2]}, {rule}: MUNI ")
    assert f["factor_pnl_sessions"] == {"count": 2, "first": TRADED[1].isoformat(), "last": TRADED[2].isoformat()}
    monkeypatch.setattr(THIS, "FILLS", FILLS + FLATTEN)
    rep, _ = run(tmp_path / "flat")
    f = rep["factor"]
    assert f["status"] == P.FLAT and len(_cum_lines(f)) == 1
    assert _cum_lines(f)[0].startswith(f"Cumulative factor P&L (book, E(t-1) x f(t), model reading) over 1 session(s), "
                                       f"{TRADED[1]} to {TRADED[1]}, {rule}: MUNI ")
    assert f["factor_pnl_sessions"] == {"count": 1, "first": TRADED[1].isoformat(), "last": TRADED[1].isoformat()}
    assert P.FACTOR_PNL_SESSIONS == rule


@pytest.mark.parametrize("night", ["held_interlude", "flat_after_one_close"])
def test_no_session_held_at_both_closes_says_why_there_is_no_factor_pnl(tmp_path, monkeypatch, night):
    """Second review of PR #82 (2026-11-11): after held -> flat -> held, no session was held at
    both its previous close and its own, so the readout has no factor P&L row; the held block
    printed no cumulative line at all and its JSON said `factor_pnl: null` with no reason. Now
    the block says it was not read and why, in a line and in `factor_pnl_why`; a flat block whose
    history is one held close does the same. Fails on the parent 51b209f (no line, no reason)."""
    fills = INTERLUDE if night == "held_interlude" else FILLS[:2] + [
        ("f3", "AAA", "sell", 5000, "10.20", TRADED[1]), ("f4", "BBB", "buy", 2000, "20.20", TRADED[1])]
    monkeypatch.setattr(THIS, "FILLS", fills)
    rep, code = run(tmp_path)
    f = rep["factor"]
    assert code == P.EXIT_OK and rep["attribution"]["reconciled"] is True
    assert f["status"] == ("OK" if night == "held_interlude" else P.FLAT), f["lines"]
    cum = _cum_lines(f)
    assert len(cum) == 1, f["lines"]
    assert cum[0].startswith("Cumulative factor P&L not read: no session since the first trade held a position at "
                             "both its previous close and its own, so no E(t-1) x f(t) was read")
    assert f["factor_pnl"] is None and cum[0] == f"Cumulative factor P&L not read: {f.get('factor_pnl_why')}"
    assert "factor_pnl_sessions" not in f


def test_the_block_refuses_a_readout_whose_last_date_is_not_the_as_of_close():
    """The guard behind finding 2 (independent review of PR #82, 2026-11-11): `_factor_report`
    is given the as-of close and refuses a readout that ends earlier, rather than print that
    earlier close's reading as the as-of one. Fails on the parent commit, which took the
    readout's own last date."""
    fs = ER.factor_set("cef")
    eq = dict(equity_series())
    rows = [dict(date=d.isoformat(), symbol=s, shares=float(n), equity=eq[d])
            for d, qq in zip(TRADED[:2], _positions_at_closes()[:2]) for s, n in qq.items() if n]
    ro = ER.readout(price_history(fs), pd.DataFrame(rows), GROUPS, fs=fs)
    with pytest.raises(ER.ReadoutError, match=f"is not the as-of close {ASOF}"):
        P._factor_report(ro, fs, "cef", ASOF)


def test_the_job_asks_the_fetch_for_its_partial_mode(tmp_path, monkeypatch):
    """The job, not the research CLI, turns the partial fetch on. Fails on the parent commit."""
    seen = {}

    def fake_fetch_each(tickers, start, asof, *, required=(), partial=False):
        seen.update(required=tuple(required), partial=partial)
        return price_history(ER.factor_set("cef")), {}, {}
    monkeypatch.setattr(ER, "fetch_each", fake_fetch_each)
    P.run_report("cef", tmp_path / "cef", ASOF, now_utc=NOW, reader=FakeReader(), groups=GROUPS,
                 nav_fetcher=fake_navs, dist_check_fetcher=fake_dividends, price_fetcher=None)
    assert seen == {"required": ER.factor_set("cef").etfs, "partial": True}


def test_a_factor_set_with_no_lag_is_unmeasured_named(tmp_path, monkeypatch):
    monkeypatch.setattr(ER, "C4_DIMSON_LAGS", None)
    rep, _ = P.run_report("c4", tmp_path / "c4", ASOF, now_utc=NOW, reader=FakeReader(), groups=FAMILIES,
                          nav_fetcher=fake_navs, dist_check_fetcher=fake_dividends,
                          price_fetcher=lambda t, s, a: (price_history(ER.factor_set("c4")), {}, {}))
    assert rep["factor"]["status"] == P.UNMEASURED and "no Dimson lag" in rep["factor"]["why"]


def test_the_fee_check_reports_and_never_changes_the_fee_line(tmp_path):
    good, _ = run(tmp_path)
    assert any("agree to the cent" in ln and "3 of 3" in ln for ln in good["attribution"]["lines"])
    bad_rows = [{"id": "fee-1", "activity_type": "FEE", "date": TRADED[0].isoformat(), "net_amount": "-99.0"}]
    rep, _ = run(tmp_path, reader=FakeReader(fee_rows=bad_rows))
    assert any("DIFFER" in ln for ln in rep["attribution"]["lines"])
    assert rep["attribution"]["session"]["fees"] == good["attribution"]["session"]["fees"]
    rep, _ = run(tmp_path, reader=FakeReader(fee_error="boom"))
    assert any("FEE activity check UNMEASURED" in ln and "boom" in ln for ln in rep["attribution"]["lines"])


def test_a_session_with_no_fee_row_is_unmeasured_not_a_measured_zero(tmp_path):
    """The FEE rows post after the trade date, so a session's rows may not exist at 20:30.
    Fails on the parent commit, which printed `account +0.00` for it and called it a
    difference. TRADED[2] has no fills, so no fee is modelled and no row is owed."""
    rows = [{"id": "fee-1", "activity_type": "FEE", "date": TRADED[0].isoformat(),
             "net_amount": str(float(fees_of([r for r in FILLS if r[5] == TRADED[0]])))}]
    rep, _ = run(tmp_path, reader=FakeReader(fee_rows=rows))
    line = next(ln for ln in rep["attribution"]["lines"] if ln.startswith("FEE activities"))
    assert f"no FEE row yet (UNMEASURED) on {TRADED[1].isoformat()}" in line
    assert "DIFFER" not in line and "account +0.00" not in line
    assert "2 of 2 session(s) agree" in line                  # TRADED[0] by its row; TRADED[2] owes nothing


def test_the_job_refuses_a_state_directory_under_data(tmp_path, monkeypatch):
    """The report holds the account's equity and P&L; data/ is the panels the book decides
    on (landmine 9). Fails on the parent commit, which wrote the report there."""
    d = tmp_path / "data"
    d.mkdir()
    monkeypatch.setattr(LA, "DATA_DIR", d)
    with pytest.raises(LA.AttributionError, match="under data/"):
        P.run_report("cef", d / "x", ASOF, now_utc=NOW, reader=FakeReader(), groups=GROUPS, nav_fetcher=fake_navs,
                     dist_check_fetcher=fake_dividends, price_fetcher=lambda *a: (None, {}, {}))
    assert not any(d.iterdir())
    assert P.main(["--book", "cef", "--state-dir", str(d / "x"), "--asof", ASOF.isoformat()], now_utc=NOW,
                  reader=FakeReader()) == 2
    assert not any(d.iterdir())


def test_the_job_refuses_a_state_directory_git_can_see(tmp_path, monkeypatch):
    """This repository is public, and the report holds the account's equity. Fails on the
    parent commit. An ignored directory, and one outside the repository, stay allowed."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    (root / ".gitignore").write_text("ignored/\n")
    monkeypatch.setattr(LA, "REPO", root)
    kw = dict(now_utc=NOW, reader=FakeReader(), groups=GROUPS, nav_fetcher=fake_navs, dist_check_fetcher=fake_dividends,
              price_fetcher=lambda t, s, a: (price_history(ER.factor_set("cef")), {}, {}))
    with pytest.raises(LA.AttributionError, match="git can see them"):
        P.run_report("cef", root / "visible", ASOF, **kw)
    assert not (root / "visible").exists()
    P.run_report("cef", root / "ignored" / "state", ASOF, **kw)
    assert (root / "ignored" / "state" / "reports" / "pnl" / f"{ASOF}.md").is_file()


def test_yfinance_keeps_its_caches_under_the_report_directory(tmp_path, monkeypatch):
    """yfinance's SQLite caches go beside the report, set before its first fetch. Fails on the
    parent commit: nothing set the location, and they went to the user cache directory."""
    calls = []

    class YF:
        dividends = None

        def set_tz_cache_location(self, d):
            calls.append(("cache", d))

        def Ticker(self, s):
            calls.append(("ticker", s))
            return self

        def history(self, **kw):
            return pd.DataFrame({"Close": []})

    monkeypatch.setitem(sys.modules, "yfinance", YF())
    P.run_report("cef", tmp_path / "cef", ASOF, now_utc=NOW, reader=FakeReader(), groups=GROUPS,
                 price_fetcher=lambda t, s, a: (price_history(ER.factor_set("cef")), {}, {}))
    where = tmp_path / "cef" / "reports" / "pnl" / "_yf_cache"
    assert calls[0] == ("cache", str(where)) and where.is_dir()
    assert any(k == "ticker" for k, _ in calls)                # the fetch did run, after the location


def test_a_failed_cache_location_is_named_and_the_report_still_runs(tmp_path, monkeypatch):
    class YF:
        dividends = None

        def set_tz_cache_location(self, d):
            raise OSError("no such thing")

        def Ticker(self, s):
            return self

        def history(self, **kw):
            return pd.DataFrame({"Close": []})

    monkeypatch.setitem(sys.modules, "yfinance", YF())
    rep, _ = P.run_report("cef", tmp_path / "cef", ASOF, now_utc=NOW, reader=FakeReader(), groups=GROUPS,
                          price_fetcher=lambda t, s, a: (price_history(ER.factor_set("cef")), {}, {}))
    assert any("yfinance's cache location" in g and "no such thing" in g for g in rep["gaps"])
    assert rep["attribution"]["status"] == "OK"


def test_an_old_session_row_is_labelled_not_substituted(tmp_path):
    # the reader has no EOD point for the session asked for: the session section is the
    # latest point, and the note says so
    class Early(FakeReader):
        def eod_equity_history(self, start, end):
            return [p for p in super().eod_equity_history(start, end) if p.date < ASOF]
    rep, _ = run(tmp_path, reader=Early())
    att = rep["attribution"]
    assert att["session"]["date"] == TRADED[1].isoformat()
    assert any("has no point" in ln and ASOF.isoformat() in ln for ln in att["lines"])


def test_cli_requires_a_state_dir(capsys, monkeypatch):
    monkeypatch.delenv("QUANTT_STATE_DIR", raising=False)
    assert P.main(["--book", "cef"]) == 2
    assert "no --state-dir" in capsys.readouterr().err
