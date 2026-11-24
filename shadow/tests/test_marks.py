"""The marks: the primary is the mark, the check only reports, a gap stays a gap,
and a stored mark never moves. Literals only."""
import datetime as dt

import pandas as pd
import pytest

from shadow import marks

D1, D2 = dt.date(2026, 1, 5), dt.date(2026, 1, 6)
PRINTS = {D1: {"AAA": 10.00, "BBB": 20.00}, D2: {"AAA": 10.10}}          # BBB has no print on D2


def _primary(syms, day):
    return {s: p for s, p in PRINTS[day].items() if s in syms}


def _check(syms, a, b):
    return pd.DataFrame([{"date": D1, "symbol": "AAA", "close": 10.00},
                         {"date": D1, "symbol": "BBB", "close": 20.30},   # 150bp away
                         {"date": D2, "symbol": "AAA", "close": 10.10},
                         {"date": D2, "symbol": "BBB", "close": 20.50}])


def _divs(syms, a, b):
    return [{"symbol": "AAA", "ex_date": D2, "amount": 0.05}, {"symbol": "AAA", "ex_date": D2, "amount": 0.02}]


def _build():
    return marks.build(["AAA", "BBB"], [D1, D2], primary=_primary, check=_check, distributions=_divs,
                       tol_bp=25.0, primary_name="auction", check_name="yf")


def test_the_primary_is_the_mark_and_a_disagreement_is_only_reported():
    m, bad, gaps = _build()
    row = m[(m["date"] == D1) & (m["symbol"] == "BBB")].iloc[0]
    assert row["close"] == 20.00 and row["source"] == "auction"
    assert list(bad["symbol"]) == ["BBB"] and bad.iloc[0]["diff_bp"] == pytest.approx(150.0)


def test_a_symbol_with_no_primary_print_has_no_row_and_the_check_does_not_fill_it():
    m, bad, gaps = _build()
    assert gaps == [(D2, "BBB")]
    assert m[(m["date"] == D2) & (m["symbol"] == "BBB")].empty


def test_two_distributions_on_one_ex_date_add():
    m, _, _ = _build()
    assert m[(m["date"] == D2) & (m["symbol"] == "AAA")].iloc[0]["dividend"] == pytest.approx(0.07)
    assert m[(m["date"] == D1) & (m["symbol"] == "AAA")].iloc[0]["dividend"] == 0.0


def test_a_stored_mark_is_never_rewritten(tmp_path):
    m, _, _ = _build()
    p = tmp_path / "marks.parquet"
    marks.append(p, m[m["date"] == D1])
    out = marks.append(p, m)                       # D1 again, unchanged, plus D2
    assert len(out) == 3
    moved = m.copy()
    moved.loc[(moved["date"] == D1) & (moved["symbol"] == "AAA"), "close"] = 10.5
    with pytest.raises(ValueError, match="never rewritten"):
        marks.append(p, moved)
