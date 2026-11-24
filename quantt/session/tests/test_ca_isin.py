"""A bond's ISIN in a corporate-action party field is a bond, not a missing party.

THE DEFECT (found 2026-11-02, fixed 2026-11-08 on the team lead's "Start the fix").
Alpaca's real feed sends a bond's ISIN in a row's `symbol` field (57 partial calls
and one reorganization over process dates 2025-11-01 -> 2028-11-08, read 2026-11-08
[V]). `_ca_symbol` read a value as a ticker or not at all, and `_ca_read` turned
every "not a ticker" into a missing party, so `corp_actions.blocking_events`
judged a partial call on a corporate bond as each of the gate's names, in the
subject role, on the long window: under `halt` it refused the session.

WHAT THESE TESTS PIN (alpaca.py, A BOND'S ISIN IN A PARTY FIELD; corp_actions.py,
A BOND IS NOT A MISSING PARTY). Only a value that cannot be a share of one of our
funds is classified as a bond: ISO 6166 shape and check digit, a US ISIN, its CUSIP
part equal to the row's own CUSIP field, and an alphabetic (debt-format) issue
code. Each of those is checked separately below. The fixture rows are the REAL
rows as the feed served them on 2026-11-08 (ids, identifiers, dates, ratios
unchanged); a variant changes one field only.

WHAT MUST NOT CHANGE. A value that is not a bond's ISIN stays a missing party:
the row stays unresolved and blocks exactly as before, for the same windows,
and its record now says what was actually there (`saw`), which the old record did
not. Here the fake session serves no CUSIP table, so a CUSIP in a party field stays
unresolved (test_ca_cusip_table.py pins the table's proof, including that case).

Hermetic: netguard refuses any socket; the key file holds test constants.
"""
import datetime as dt

import pytest

from quantt.broker import alpaca as al
from quantt.session import corp_actions as cam
from quantt.tests.test_alpaca_client import KEY_ID, SECRET, FakeResp, FakeSession, route

UNI = ["AAA", "BBB", "CCC"]
POS = {"CCC": 10}
TARGETS = ["AAA"]
# Last filled order in CCC submitted 2026-10-20: L_X is 2026-10-19 (the trading day before).
CLOSED = [{"client_order_id": "cef-20261020-CCC-1", "symbol": "CCC", "side": "buy",
           "status": "filled", "filled_qty": "10", "submitted_at": "2026-10-20T19:53:00Z"}]
# Friday 2026-10-30, as-of Thursday 2026-10-29; Monday 2026-11-02, as-of Friday 10-30.
D1030, A1030 = dt.date(2026, 10, 30), dt.date(2026, 10, 29)
D1102, A1102 = dt.date(2026, 11, 2), dt.date(2026, 10, 30)

# The three real rows, as Alpaca served them on 2026-11-08 (GET /v1/corporate-actions).
PCALL_ROW = {"cusip": "U67540AA9", "id": "db0847b7-9523-4b2f-afba-ae51ddb77ec5",
             "lottery_date": "2026-10-22", "lottery_type": "original",
             "payable_date": "2026-10-30", "price": 1000, "process_date": "2026-10-30",
             "record_date": "2026-10-21", "results_publication_date": "2026-10-22",
             "symbol": "USU67540AA98"}
SNTI_SPIN_ROW = {"ex_date": "2026-10-30", "id": "e34ddd44-1ed2-4b30-b668-be3f16e11dce",
                 "new_cusip": "816CVR021", "new_rate": 1, "new_symbol": "816CVR021",
                 "payable_date": "2026-11-02", "process_date": "2026-11-02",
                 "record_date": "2026-10-30", "source_cusip": "816944102", "source_rate": 1,
                 "source_symbol": "SNTI"}
JAGX_MERGER_ROW = {"acquiree_cusip": "47010C847", "acquiree_rate": 1,
                   "acquiree_symbol": "47010C847", "acquirer_cusip": "47010C854",
                   "acquirer_rate": 5, "acquirer_symbol": "JAGX", "effective_date": "2026-11-02",
                   "id": "6abeb209-f747-4bf3-a231-67b8c0984d4a", "payable_date": "2026-11-02",
                   "process_date": "2026-11-02"}


def _isin_with_check(stem: str) -> str:
    """`stem` (11 chars) plus its ISO 6166 check digit: a mechanically valid ISIN."""
    digits = "".join(str(int(ch, 36)) for ch in stem)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch) * (2 if i % 2 == 0 else 1)
        total += d - 9 if d > 9 else d
    return stem + str((10 - total % 10) % 10)


def _parser(tmp_path, feed):
    """The real AlpacaClient corporate-action read over a fake HTTP session serving
    `feed` (one page)."""
    kf = tmp_path / "alpaca-test.env"              # test constants, never config/.env
    kf.write_text(f"ALPACA_CEF_KEY_ID={KEY_ID}\nALPACA_CEF_SECRET_KEY={SECRET}\n")
    session = FakeSession(route({"/v1/corporate-actions": lambda p: FakeResp(
        200, {"corporate_actions": feed, "next_page_token": None})}))
    return al.AlpacaClient("cef", kf, session=session, sleep=lambda s: None)


def _check(tmp_path, feed, session_date=D1030, asof=A1030, mode=cam.HALT):
    """`corp_actions.check` over the real parser, for a book holding CCC and targeting AAA."""
    return cam.check(_parser(tmp_path, feed).corporate_actions, CLOSED, POS, TARGETS, asof,
                     session_date, mode, universe=UNI)


# ---------------------------- the positive path: a bond is not a missing party


def test_the_real_partial_call_on_a_bonds_isin_blocks_nothing_and_is_recorded(tmp_path):
    """db0847b7: the partial call on USU67540AA98. On origin/main (a5b94c8) it was `missing`, judged as
    CCC and AAA, and blocked; here it is recorded under `bond_rows` and blocks nothing."""
    rec = _check(tmp_path, {"partial_calls": [PCALL_ROW]})
    assert rec["status"] == cam.CLEAR and rec["blocking"] == []
    assert "unresolved" not in rec
    assert rec["events"] == []                        # never entered `parties`
    (k,) = rec["bond_rows"]
    assert k["id"] == PCALL_ROW["id"] and k["bonds"] == [
        {"field": "symbol", "role": "subject", "isin": "USU67540AA98"}]
    assert k["type"] == "partial_call" and k["malformed"] == {}
    assert "skipped_malformed" not in rec            # a bond row is not a malformed row
    assert not any("UNRESOLVED" in line for line in cam.lines(rec))
    assert any("1 row(s) name a bond by its ISIN" in line for line in cam.lines(rec))


def test_a_reorganizations_own_isin_is_read_as_a_bond(tmp_path):
    """The one real reorganization row with an ISIN in `symbol` (US81880AAA07, 2026-06)."""
    row = {"cash_rate": 4.34345534, "cusip": "81880AAA0", "effective_date": D1030.isoformat(),
           "id": "cb8733d9-b672-4e4d-a398-68fbc80ef835", "payable_date": "2026-11-01",
           "process_date": D1030.isoformat(), "symbol": "US81880AAA07"}
    rec = _check(tmp_path, {"reorganizations": [row]})
    assert rec["status"] == cam.CLEAR and "unresolved" not in rec
    assert [k["bonds"][0]["field"] for k in rec["bond_rows"]] == ["symbol"]


def test_a_stock_movement_leg_carrying_a_bonds_isin_is_a_bond_not_an_unreadable_leg(tmp_path):
    row = {"cusip": "x", "effective_date": D1030.isoformat(), "id": "reorg-leg-1",
           "process_date": D1030.isoformat(), "symbol": "XYZ",
           "stock_movements": [{"symbol": "USU67540AA98", "cusip": "U67540AA9",
                                "new_rate": 1, "source_rate": 1}]}
    rec = _check(tmp_path, {"reorganizations": [row]})
    assert rec["status"] == cam.CLEAR and "unresolved" not in rec
    assert rec["bond_rows"][0]["bonds"] == [
        {"field": "stock_movements[0].symbol", "role": "allocated", "isin": "USU67540AA98"}]


def test_a_bond_row_repeated_across_pages_is_recorded_once(tmp_path):
    """Same-row page repeats are collapsed, as for every other recorded row."""
    rec = _check(tmp_path, {"partial_calls": [PCALL_ROW, dict(PCALL_ROW)]})
    assert len(rec["bond_rows"]) == 1


def test_a_bond_row_with_a_malformed_price_is_recorded_as_a_bond_and_blocks_nothing(tmp_path):
    """Its every party is a bond and none ours (`SKIPPED AND RECORDED`), so a bad price is
    recorded on the bond row (`malformed`), not read as a missing fund."""
    rec = _check(tmp_path, {"partial_calls": [{**PCALL_ROW, "price": "not-a-number"}]})
    assert rec["status"] == cam.CLEAR and "unresolved" not in rec
    (k,) = rec["bond_rows"]
    assert k["malformed"] == {"price": "not-a-number"}


# ---------------------- each condition, on its own: fails closed, says what it saw


def _assert_stays_unresolved_and_names_what_it_saw(rec, row_id, field, value):
    """The row is still a missing party for each of the gate's names (BE CONSERVATIVE),
    and the record now says what was there, which the old record did not."""
    assert rec["status"] == cam.BLOCKING
    assert {u["id"] for u in rec["unresolved"]} == {row_id}
    assert {b["symbol"] for b in rec["blocking"]} == {"AAA", "CCC"}
    assert all(b["unresolved"] == field and value in b["saw"] for b in rec["blocking"])
    (u,) = rec["unresolved"]
    assert u["missing"][0]["field"] == field and value in u["saw"][field]
    assert "bond_rows" not in rec


@pytest.mark.parametrize("label,value,cusip", [
    ("a bad ISO 6166 check digit", "USU67540AA99", "U67540AA9"),
    ("the CUSIP part disagrees with the row's own CUSIP field", "USU67540AA98", "U67540AB9"),
    ("no CUSIP on the row to corroborate it", "USU67540AA98", None),
    ("not a US ISIN, though its check digit holds", _isin_with_check("XS0123456AA"), "0123456AA"),
    ("an equity-format (numeric) issue code", "US0378331005", "037833100"),
    ("twelve characters that are not an ISIN at all", "NOTANISINXXX", "NOTANISIN"),
])
def test_a_value_that_is_not_a_bonds_isin_stays_unresolved(tmp_path, label, value, cusip):
    rec = _check(tmp_path, {"partial_calls": [{**PCALL_ROW, "symbol": value, "cusip": cusip}]})
    _assert_stays_unresolved_and_names_what_it_saw(rec, PCALL_ROW["id"], "symbol", value)


def test_the_real_snti_cvr_row_stays_unresolved_a_cusip_is_not_an_isin(tmp_path):
    """e34ddd44: the CVR in Senti's spin-off row is a CUSIP-format value (816CVR021). With no
    CUSIP table served here it stays unresolved: the table's proof is test_ca_cusip_table."""
    rec = _check(tmp_path, {"spin_offs": [SNTI_SPIN_ROW]})
    assert rec["status"] == cam.BLOCKING
    _assert_stays_unresolved_and_names_what_it_saw(
        rec, SNTI_SPIN_ROW["id"], "new_symbol", "816CVR021")


def test_the_real_jagx_preferred_row_stays_unresolved_a_cusip_is_not_an_isin(tmp_path):
    """6abeb209: the Series R conversion, its acquiree a CUSIP (47010C847). With no CUSIP
    table served here it stays unresolved: the table's proof is test_ca_cusip_table."""
    rec = _check(tmp_path, {"stock_mergers": [JAGX_MERGER_ROW]}, session_date=D1102, asof=A1102)
    assert rec["status"] == cam.BLOCKING
    _assert_stays_unresolved_and_names_what_it_saw(
        rec, JAGX_MERGER_ROW["id"], "acquiree_symbol", "47010C847")


def test_a_bond_row_and_a_null_party_in_one_read_are_told_apart(tmp_path):
    """A null party is the ruling's original case: still missing, with no `saw`,
    because nothing was sent (pinned so `saw` never invents a value), and a bond
    row beside it in the same read does not hide it. The classifier must tell the
    two apart row by row, in the one read the gate makes."""
    null_row = {**PCALL_ROW, "id": "pc-null-1", "symbol": None}
    rec = _check(tmp_path, {"partial_calls": [PCALL_ROW, null_row]})
    assert [k["id"] for k in rec["bond_rows"]] == [PCALL_ROW["id"]]
    assert rec["status"] == cam.BLOCKING
    (u,) = rec["unresolved"]
    assert u["id"] == "pc-null-1" and u["missing"][0]["field"] == "symbol" and "saw" not in u
    assert {b["symbol"] for b in rec["blocking"]} == {"AAA", "CCC"}
    assert all("saw" not in b for b in rec["blocking"])


# --------------------------------------------------- the classifier, in isolation


def test_the_iso_6166_check_digit_on_real_isins():
    """The check digit, on real ISINs of known issuers (a bad digit fails)."""
    for good in ("US0378331005", "US5949181045", "US88160R1014", "USU67540AA98"):
        assert al._ca_isin_check_digit(good), good
    for bad in ("US0378331006", "USU67540AA99"):
        assert not al._ca_isin_check_digit(bad), bad


@pytest.mark.parametrize("value", [
    None, "", 12, True, [], {}, " USU67540AA98", "USU67540AA98\n", "usu67540aa98"])
def test_the_classifier_refuses_anything_that_is_not_an_isin_string(value):
    assert al._ca_bond_isin(value, "U67540AA9")[0] is None


def test_a_valid_bond_isin_cannot_equal_one_of_our_tickers():
    """A classified value is 12 characters and a ticker at most 10 (`_SYMBOL_RE`), so the
    two cannot collide; and the classified party never enters `parties` at all."""
    isin, _ = al._ca_bond_isin("USU67540AA98", "U67540AA9")
    assert isin == "USU67540AA98" and al._SYMBOL_RE.fullmatch(isin) is None
