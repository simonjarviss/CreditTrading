"""The corporate-action gate: a malformed row that cannot be ours is skipped and recorded; an acknowledged action clears.

Two team-lead rulings of 2026-10-29, answered interactively on the review of
4c63b1f (corp_actions.py, "MALFORMED ROWS" and "ACKNOWLEDGEMENTS"):

A. A corporate-action row with an empty or null required symbol used to fail
   the whole read, so under `halt` one bad row for ANY issuer refused every
   session until Alpaca fixed it. Now it is skipped, and recorded in plan.json,
   the run record and one log line naming its id and the missing field, when
   every symbol present in it is outside the book's universe. It still refuses
   when it could be ours: a present symbol is one of the universe's, which
   covers a merger with our fund on one side and the other symbol null.
B. A backfilled name change, redemption, worthless removal or partial call is
   dated by its process date, falls on the long window, and under `halt` never
   clears by itself. It clears by the team lead's recorded acknowledgement:
   `<state>/ca_acks.json`, written only by `python3 -m quantt.session ca-ack`.
   The gate clears that action id only; anything else, a new action on the
   same fund included, still halts. An unreadable file refuses.

Every test here FAILS on 4c63b1f (`git archive 4c63b1f`, this file copied
in). The two no-op tests compare with pins COMPUTED BY 4c63b1f's CODE: with no
malformed row, no acknowledgement and no backfilled action, the orders sent,
send.json, plan.json, orders.jsonl, STARTED (bar its pid) and every run record
are byte-identical to 4c63b1f. Their pins match there; they fail there only
where they assert that the new path ran (the read's keywords, the file read).

HOW THE PINS WERE MADE (2026-10-29). `_outputs` run on this worktree while it
was exactly 4c63b1f (clean), under PYTHONHASHSEED unset, 0 and 1: identical
every time. Re-derive only after a deliberate change to what a session writes,
by running `_outputs` on the commit before that change; never edit by hand.

Hermetic. The broker is test_corp_actions.CAClient (test_run.FakeClient plus
the corporate-action read) whose `corporate_actions` is the REAL
`AlpacaClient.corporate_actions` parser over a fake HTTP session, so the rows
go through the code prod runs. Its key file is a temporary file holding test
constants, never config/.env; netguard refuses any socket. The rows are the
reference's examples (test_alpaca_client.CA_REFERENCE) and synthetic rows
built from its field lists: they test the code, never a claim about the market.
"""
import datetime as dt
import hashlib
import json
import shutil

import pytest

from quantt.broker import alpaca as al
from quantt.session import corp_actions as cam
from quantt.session import run as rn
from quantt.session.tests.test_corp_actions import CLOSED, HELD, L_SET, CAClient
from quantt.session.tests.test_run import ASOF, BOOK, D, EVE, LATE, SPEC, make, to_send_time
from quantt.tests.test_alpaca_client import (CA_REFERENCE, KEY_ID, SECRET, FakeResp,
                                             FakeSession, route)

DAY = D.isoformat()
PATHS = ("late_send", "cls")
# A well-formed action on a held name, before its shares were last set: in the
# record's events, blocking nothing (test_corp_actions, the same date).
OLD_SPLIT_CCC = {"ex_date": (L_SET - dt.timedelta(days=3)).isoformat(), "id": "rs-ccc-old",
                 "new_rate": 1, "old_rate": 2, "process_date": (L_SET - dt.timedelta(days=3))
                 .isoformat(), "symbol": "CCC", "cusip": "CCC000000"}


def _feed(extra=None):
    """CA_REFERENCE plus the old CCC split, plus `extra` {key: [rows]}."""
    ca = {k: list(v) for k, v in CA_REFERENCE.items()}
    ca["reverse_splits"] = ca["reverse_splits"] + [OLD_SPLIT_CCC]
    for k, rows in (extra or {}).items():
        ca[k] = ca.get(k, []) + rows
    return ca


class RealParserClient(CAClient):
    """CAClient whose corporate-action read is the real AlpacaClient parser over
    a fake HTTP session serving `feed` (one page). `feed` may be replaced
    between sessions."""

    def __init__(self, state, *, feed, key_file, **kw):
        super().__init__(state, **kw)
        self.feed = feed
        session = FakeSession(route({"/v1/corporate-actions": lambda p: FakeResp(
            200, {"corporate_actions": self.feed, "next_page_token": None})}))
        self._real = al.AlpacaClient("cef", key_file, session=session, sleep=lambda s: None)

    last_kw = None             # the keywords of the latest read, for the no-op test

    def corporate_actions(self, symbols, start, end, **kw):
        self.ca_at = len(self.calls)
        self.calls.append(("corporate_actions", tuple(symbols), start, end))
        RealParserClient.last_kw = kw
        return self._real.corporate_actions(symbols, start, end, **kw)


def _key_file(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "alpaca-test.env"            # test constants, never config/.env
    p.write_text(f"ALPACA_CEF_KEY_ID={KEY_ID}\nALPACA_CEF_SECRET_KEY={SECRET}\n")
    return p


def _session(tmp_path, path, feed, *, acks=None):
    """(client, deps, state, out, decide exit) ready to transmit on `path`, gate
    under `halt`, armed. `feed` is what Alpaca lists and `acks` the text of
    <state>/ca_acks.json at the transmitting run. late_send: the evening decide
    runs first on the clean reference feed with no acknowledgement file, and
    the feed and the file change before the 15:53 send, as an action listed or
    acknowledged after the decide would (the send re-reads both)."""
    c = RealParserClient(tmp_path / "state", feed=feed if path == "cls" else _feed(),
                         key_file=_key_file(tmp_path), positions=HELD, closed=CLOSED)
    kw = {"execution": LATE, "now_utc": EVE.astimezone(dt.timezone.utc)} \
        if path == "late_send" else {}
    if path == "late_send":
        c._clock = EVE
    c, deps, state, _, out = make(tmp_path, client=c, **kw)
    deps.corp_actions = cam.HALT
    (state / "AUTO_ARMED").touch()
    decide_exit = None
    if path == "late_send":
        decide_exit = rn.run_session(BOOK, SPEC, deps)
        assert decide_exit == rn.EXIT_PLANNED, "".join(out)
        c.feed = feed
        to_send_time(c, deps)
    if acks is not None:
        (state / cam.ACKS_FILE).write_text(acks)
    return c, deps, state, out, decide_exit


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _outputs(tmp_path, path, *, acks=None) -> dict:
    """Hashes of everything the session(s) wrote and sent on the reference feed
    (no malformed row, nothing blocking). STARTED without its pid."""
    c, deps, state, out, decide_exit = _session(tmp_path, path, _feed(), acks=acks)
    code = rn.run_session(BOOK, SPEC, deps)
    day = state / DAY
    started = json.loads((day / "STARTED").read_text())
    started.pop("pid")
    got = {"decide_exit": decide_exit, "exit": code,
           "sent": _sha(json.dumps([[o["client_order_id"], o["symbol"], o["side"], o["qty"],
                                     o["time_in_force"]] for o in c.accepted.values()]).encode()),
           "plan_json": _sha((day / "plan.json").read_bytes()),
           "orders_jsonl": _sha((day / "orders.jsonl").read_bytes()),
           "started": _sha(json.dumps(started, sort_keys=True).encode()),
           "runs": {p.name: _sha(p.read_bytes()) for p in sorted((day / "runs").iterdir())}}
    if path == "late_send":
        got["send_json"] = _sha((day / "send.json").read_bytes())
    assert str(tmp_path) not in "".join(p.read_text() for p in day.rglob("*") if p.is_file())
    return got


# PINNED 2026-10-29 on 4c63b1f (module docstring: how, and how to re-derive).
PINNED_4C63B1F = {
    "late_send": {
        "decide_exit": 6, "exit": 0,
        "orders_jsonl": "f6b2e3aa52ef01e3f2576f2c28dbc938461cc54eb9fd6027747ab473fa2ffce9",
        "plan_json": "54c7cdf4c165a5467b4690d1923c01419892f13dd2480e2bfa0959454df51dcc",
        "runs": {   # the evening DECIDE's record, then the SEND's
            "20260929T020000Z-run.json":
                "45c5f921d453636409a71a2b0673e80abb4ae91cb84c6e4d8d90e269efe19b30",
            "20260929T195300Z-run.json":
                "56edd61c8c6f8483012ab6b083d7f54c3e6784a5b7e653e47e6ca77a6d62a94b"},
        "send_json": "62ffe6f1e8cd89e21d5326656099fc92213cbeb4f6badf39b75f9865d8e277c8",
        "sent": "6c86cc494564dd5ccc3467b7823c14954dbaf752588fc62b092fdc8c3c797b55",
        "started": "d6fe7307ef73c5c08447a052e8600eda75af24fe1e5550124bba46f729d0cf24"},
    "cls": {
        "decide_exit": None, "exit": 0,
        "orders_jsonl": "7f67e3d846b0162c98d67881026cdb793f4d9cefa677bccfecc5f1acc2ef4ac7",
        "plan_json": "b7e3fc4fbb027a734c7e74c704298650d9ed7655b898ae9362754fd5926df305",
        "runs": {
            "20260929T123000Z-run.json":
                "50aa67d402394c2fabcff5127380d44d4ebd7c75b2298e683283af188f502f4d"},
        "sent": "022ad3f4f3da8d912ef0949fe203fc18a9c201a31f67e986a968015abce68a09",
        "started": "20108e86665c9897e9f2bacebbb84d2fb92cd10fe2765cfdafcb0ab3abbc7094"},
}


# ------------------------------------------- no malformed row, no ack: a no-op

@pytest.mark.parametrize("path", PATHS)
def test_with_no_malformed_row_and_no_ack_the_session_is_byte_identical_to_4c63b1f(tmp_path,
                                                                                    path):
    """With the reference feed (well-formed, one held-name event that blocks
    nothing) and no ca_acks.json: everything written and sent equals 4c63b1f's
    pins. The read DID take the new keywords (else the identity is vacuous):
    FAILS on 4c63b1f there, after its pins have matched."""
    got = _outputs(tmp_path, path)
    assert got == PINNED_4C63B1F[path], {k: (got[k], PINNED_4C63B1F[path].get(k))
                                         for k in got if got[k] != PINNED_4C63B1F[path].get(k)}
    plan = json.loads((tmp_path / "state" / DAY / "plan.json").read_text())
    assert plan["corporate_actions"]["status"] == cam.CLEAR
    assert [e["id"] for e in plan["corporate_actions"]["events"]] == ["rs-ccc-old"]
    assert "skipped_malformed" not in plan["corporate_actions"]
    assert "acknowledged" not in plan["corporate_actions"]
    assert RealParserClient.last_kw["skipped"] == [] and \
        set(RealParserClient.last_kw["universe"]) == set(SPEC["frozen"]["universe"])


@pytest.mark.parametrize("path", PATHS)
def test_an_ack_for_an_id_not_in_the_feed_is_harmless(tmp_path, path, monkeypatch):
    """An acknowledgement whose id the feed no longer lists changes nothing: the
    same pins. The file WAS read (FAILS on 4c63b1f, which has no reader)."""
    reads = []
    real = rn._read_ca_acks
    monkeypatch.setattr(rn, "_read_ca_acks", lambda p, b: reads.append(p) or real(p, b))
    got = _outputs(tmp_path, path, acks=_acks_text(["gone-from-the-feed"]))
    assert got == PINNED_4C63B1F[path]
    assert reads and all(p.name == cam.ACKS_FILE for p in reads)


# ------------------------------------------------ A. malformed rows (ruling A)

# Built from the reference's own rows: an unrelated merger whose acquirer is
# null, and the same shape with our names on one side.
UNRELATED_NULL_ACQUIRER = dict(CA_REFERENCE["stock_mergers"][0], id="sm-null-acquirer",
                               acquirer_symbol=None)
OURS_NULL_ACQUIRER = dict(UNRELATED_NULL_ACQUIRER, id="sm-ccc-null", acquiree_symbol="CCC")
OURS_EMPTY_ACQUIREE = dict(UNRELATED_NULL_ACQUIRER, id="sm-ccc-acquirer",
                           acquirer_symbol="CCC", acquiree_symbol="")
# A row whose every party is present and none ours, a NON-party field spoiled:
# the only kind skipped and recorded (release-check of 04aca24, 2026-11-01).
UNRELATED_BAD_DATE = dict(CA_REFERENCE["stock_mergers"][0], id="sm-bad-date",
                          effective_date="2023-7-20")
# A reorganization of a TARGETED name whose stock leg has neither ticker nor CUSIP.
OURS_REORG_BAD_LEG = {"id": "reorg-aaa-bad-leg", "symbol": "AAA", "cusip": "AAA000000",
                      "effective_date": "2023-09-01", "process_date": "2023-09-01",
                      "stock_movements": [{"symbol": None, "new_rate": 1, "source_rate": 1}]}


def _refusals(state, path):
    """The transmitting run's refusals: send.json (late send) or plan.json (cls)."""
    name = "send.json" if path == "late_send" else "plan.json"
    return json.loads((state / DAY / name).read_text())["refusals"]


def _transmit(tmp_path, path, feed):
    c, deps, state, out, decide_exit = _session(tmp_path, path, feed)
    n = len(out)
    code = rn.run_session(BOOK, SPEC, deps)
    return c, state, "".join(out[n:]), decide_exit, code


def _gate_records(state, path):
    """The corporate-action record in every file the transmitting run wrote:
    plan.json (cls) or send.json (late), and that run's record."""
    day = state / DAY
    runs = sorted((day / "runs").iterdir())
    files = [day / ("send.json" if path == "late_send" else "plan.json"), runs[-1]]
    return {f.name: json.loads(f.read_text())["corporate_actions"] for f in files}


@pytest.mark.parametrize("path", PATHS)
def test_a_malformed_row_for_unrelated_issuers_is_skipped_and_recorded(tmp_path, path):
    """Ruling A, as applied since 2026-11-01: every party (LSI, EXR) present
    and outside the universe, a non-party field (the date) malformed: skipped,
    the session sends, and the row is in plan.json or send.json, the run
    record and ONE log line naming its id and the field. (Corrected
    2026-11-01: this test's row was a null acquirer, which now refuses.)
    FAILS on 04aca24, which ignored the row and recorded nothing."""
    feed = _feed({"stock_mergers": [UNRELATED_BAD_DATE]})
    c, state, log, decide_exit, code = _transmit(tmp_path, path, feed)
    assert code == rn.EXIT_SENT, log
    assert decide_exit in (None, rn.EXIT_PLANNED)
    want = [{"id": "sm-bad-date", "type": "stock_merger",
             "malformed": {"effective_date": "2023-7-20"},
             "present": [["LSI", "acquiree"], ["EXR", "acquirer"]],
             "cusips": {"acquiree_cusip": "53223X107", "acquirer_cusip": "30225T102"},
             "dates": {"effective_date": "2023-7-20", "process_date": "2023-07-20"}}]
    for name, ca in _gate_records(state, path).items():
        assert ca["status"] == cam.CLEAR and ca["skipped_malformed"] == want, name
    skipped = [x for x in log.splitlines() if "SKIPPED a malformed row" in x]
    assert len(skipped) == 1 and "sm-bad-date" in skipped[0] \
        and "effective_date='2023-7-20'" in skipped[0], log


# The release-check of 9cf5cf2 (2026-11-01, reproduced by the reviewer's
# probe): a held fund's own action with its subject symbol null, its CUSIP the
# fund's, effective on the session date. 9cf5cf2 skipped both as "naming none
# of ours", read CLEAR under `halt` and SENT on both paths.
HELD_SPLIT_NULL_SYMBOL = dict(OLD_SPLIT_CCC, id="rs-ccc-null-symbol", symbol=None, ex_date=DAY,
                              process_date=DAY)
HELD_ACQUIRED_NULL_ACQUIREE = dict(UNRELATED_NULL_ACQUIRER, id="sm-ccc-acquired-null",
                                   acquiree_symbol=None, acquirer_symbol="XOM",
                                   acquiree_cusip="CCC000000", effective_date=DAY,
                                   process_date=DAY)


# The release-check of 04aca24 (2026-11-01, reproduced): a held fund as the
# ACQUIRER with its symbol null (acquiree outside the universe), and a
# reorganization leg with neither ticker nor CUSIP, both on the session date.
# 04aca24 skipped both and SENT on both paths.
HELD_ACQUIRER_NULL = dict(UNRELATED_NULL_ACQUIRER, id="sm-ccc-acquirer-null",
                          acquirer_cusip="CCC000000", effective_date=DAY, process_date=DAY)
LEG_NULL_TODAY = {"id": "reorg-leg-null-today", "symbol": "AIMTF", "cusip": "G0137D100",
                  "effective_date": DAY, "process_date": DAY,
                  "stock_movements": [{"symbol": None, "new_rate": 1, "source_rate": 1}]}


# UNRESOLVED ROWS (docs/SYSTEM.md §5, team lead 2026-11-02 (unresolved
# corporate-action rows)). Each row below has a null or empty party. In a
# window of one of the gate's names, in the missing role, it blocks, naming the
# row and the field; outside every window it is recorded only. Every test in
# this section FAILS on 709d6cb, which refused every such row as UNMEASURED,
# in or out of a window.
def _at(row, day):
    """The row with every date field set to `day`."""
    return {k: (day if k in ("ex_date", "effective_date", "process_date") else v)
            for k, v in row.items()}


UNRESOLVED_CASES = [
    ("reverse_splits", HELD_SPLIT_NULL_SYMBOL, "symbol"),
    ("stock_mergers", HELD_ACQUIRED_NULL_ACQUIREE, "acquiree_symbol"),
    ("stock_mergers", HELD_ACQUIRER_NULL, "acquirer_symbol"),
    ("reorganizations", LEG_NULL_TODAY, "stock_movements[0].symbol"),
    ("reorganizations", OURS_REORG_BAD_LEG, "stock_movements[0].symbol"),
    ("stock_mergers", OURS_NULL_ACQUIRER, "acquirer_symbol"),
    ("stock_mergers", OURS_EMPTY_ACQUIREE, "acquiree_symbol"),
]
UNRESOLVED_IDS = ["split-symbol-null", "acquiree-null", "acquirer-null", "outside-reorg-leg-null",
                  "ours-reorg-leg-null", "ours-acquiree-acquirer-null",
                  "ours-acquirer-acquiree-empty"]


@pytest.mark.parametrize("key,row,field", UNRESOLVED_CASES, ids=UNRESOLVED_IDS)
@pytest.mark.parametrize("path", PATHS)
def test_an_unresolved_row_in_a_window_refuses_naming_the_row_and_the_field(tmp_path, path, key,
                                                                          row, field):
    """Dated the session date: treated as each of the gate's names, the missing
    party blocks. REFUSED, nothing sent; the refusal is the gate's own
    (not UNMEASURED), naming the row, the missing field and how to clear it."""
    row = _at(row, DAY)
    c, state, log, decide_exit, code = _transmit(tmp_path, path, _feed({key: [row]}))
    assert code == rn.EXIT_REFUSED and c.submits() == [], log
    data = [r["detail"] for r in _refusals(state, path) if r["gate"] == "data"]
    assert len(data) == 1 and "UNMEASURED" not in data[0], data
    assert f"an UNRESOLVED" in data[0] and f"its {field} is missing" in data[0] \
        and f"ca-ack --id {row['id']}" in data[0], data
    (u,) = _ca_record(state, path)["unresolved"]
    assert u["id"] == row["id"] and u["blocks"] is True


@pytest.mark.parametrize("key,row,field", UNRESOLVED_CASES, ids=UNRESOLVED_IDS)
@pytest.mark.parametrize("path", PATHS)
def test_an_unresolved_row_outside_every_window_is_recorded_only(tmp_path, path, key, row,
                                                                 field):
    """Dated 2023: no name's window holds it, so it blocks for none. The
    session SENDS, and the row is in the record and one log line."""
    row = _at(row, "2023-07-20")
    c, state, log, decide_exit, code = _transmit(tmp_path, path, _feed({key: [row]}))
    assert code == rn.EXIT_SENT, log
    ca = _ca_record(state, path)
    assert ca["status"] == cam.CLEAR and [(u["id"], u["blocks"], u["missing"][0]["field"])
                                          for u in ca["unresolved"]] == [(row["id"], False, field)]
    lines = [x for x in log.splitlines() if "UNRESOLVED, recorded only" in x]
    assert len(lines) == 1 and row["id"] in lines[0] and field in lines[0], log


def _real_check(tmp_path, feed, asof, session):
    """cam.check through the REAL parser, held CCC (CLOSED) and target AAA."""
    c = RealParserClient(tmp_path / "rc", feed=feed, key_file=_key_file(tmp_path))
    return cam.check(c.corporate_actions, CLOSED, HELD, ["AAA"], asof, session, cam.HALT,
                     universe=SPEC["frozen"]["universe"])


def test_a_short_window_unresolved_row_halts_one_session_and_then_clears(tmp_path):
    """The book json's promise, kept: a null acquirer dated the session date
    blocks that session (its missing acquirer treated as CCC) and not the next.
    On 709d6cb the read raised in both, and in every later session."""
    feed = _feed({"stock_mergers": [HELD_ACQUIRER_NULL]})
    assert _real_check(tmp_path, feed, ASOF, D)["status"] == cam.BLOCKING
    nxt = _real_check(tmp_path, feed, D, D + dt.timedelta(days=1))
    assert nxt["status"] == cam.CLEAR and nxt["unresolved"][0]["blocks"] is False


def test_the_release_check_probe_an_outside_null_acquirer_never_halts(tmp_path):
    """The reviewer's probe (2026-11-02): a merger of two outside issuers,
    acquirer "", effective 2026-12-15, with PDI held since 2026-10-01. Sessions
    2026-11-04, 2026-12-17 and 2027-01-29 are CLEAR, the row recorded in each
    (the acquirer's short window never holds 12-15 for them); and `ca-ack`'s
    own read returns it. On 709d6cb all three raised, and so did that read."""
    row = {"id": "sm-outside-1", "acquiree_symbol": "ZZZQ", "acquiree_cusip": "1",
           "acquirer_symbol": "", "acquirer_cusip": "2", "effective_date": "2026-12-15",
           "process_date": "2026-12-15", "acquirer_rate": 0.5}
    c = RealParserClient(tmp_path / "p", feed={"stock_mergers": [row]},
                         key_file=_key_file(tmp_path))
    closed = [{"id": "o1", "client_order_id": "cef-20261001-PDI-1", "symbol": "PDI",
               "filled_qty": "100", "submitted_at": "2026-10-01T19:52:00Z"}]
    for asof, sess in [(dt.date(2026, 11, 3), dt.date(2026, 11, 4)),
                       (dt.date(2026, 12, 16), dt.date(2026, 12, 17)),
                       (dt.date(2027, 1, 28), dt.date(2027, 1, 29))]:
        r = cam.check(c.corporate_actions, closed, {"PDI": 100}, ["PDI"], asof, sess, cam.HALT,
                      universe=["PDI", "PHK", "MHD"])
        assert r["status"] == cam.CLEAR, sess
        assert [(u["id"], u["blocks"]) for u in r["unresolved"]] == [("sm-outside-1", False)]
    ev = c.corporate_actions(["PDI"], dt.date(2026, 9, 1), dt.date(2028, 12, 1),
                             universe=["PDI", "PHK", "MHD"], skipped=[], rows={})
    assert [e["id"] for e in ev] == ["sm-outside-1"]


# ------------------------------- one id, one event (release-check of 9630322)

@pytest.mark.parametrize("path", PATHS)
def test_two_null_id_rows_naming_ours_refuse_and_never_hide_the_blocking_one(tmp_path, path):
    """The reviewer's probe, end to end (2026-10-30). Two reverse splits with
    `id: null`: the first on the held CCC before its shares were last set
    (blocks nothing), the second on the targeted AAA effective on the session
    date (must block). On 9630322 the second was dropped as a "duplicate" of
    the first, the gate read CLEAR under `halt` and the session SENT. From
    9cf5cf2 to 7df8926 the read raised (UNMEASURED), which only a release could
    unstick. Now each row is keyed by its content and neither is dropped: the
    session REFUSES on the AAA split, naming its key, and records the CCC one
    as not blocking. FAILS on 7df8926 (UNMEASURED)."""
    rows = [dict(OLD_SPLIT_CCC, id=None),
            dict(OLD_SPLIT_CCC, id=None, symbol="AAA", cusip="AAA000000", ex_date=DAY,
                 process_date=DAY)]
    k_ccc, k_aaa = (al.ca_row_key(r) for r in rows)
    c, state, log, decide_exit, code = _transmit(tmp_path, path, _feed({"reverse_splits": rows}))
    assert code == rn.EXIT_REFUSED and c.submits() == [], log
    data = [r["detail"] for r in _refusals(state, path) if r["gate"] == "data"]
    assert len(data) == 1 and "UNMEASURED" not in data[0], data
    assert f"AAA (target) is the subject in reverse_split {k_aaa}" in data[0] \
        and f"ca-ack --id {k_aaa}" in data[0] and k_ccc not in data[0], data
    ca = _ca_record(state, path)
    assert sorted((u["id"], u["blocks"]) for u in ca["unresolved"]) == sorted(
        [(k_ccc, False), (k_aaa, True)])


# -------------------------------------------- B. acknowledgements (ruling B)

# A backfilled name change on the held name CCC: no ex or effective date, so
# its process date is its market date, inside CCC's long window [L_SET, D].
BACKFILL_NC = {"id": "nc-ccc-backfill", "old_symbol": "CCC", "new_symbol": "CCCN",
               "old_cusip": "CCC000000", "new_cusip": "CCC000001",
               "process_date": "2026-09-24"}
NEW_SPLIT_CCC = dict(OLD_SPLIT_CCC, id="rs-ccc-new", ex_date="2026-09-25",
                     process_date="2026-09-25")
ACKED_AT = "2026-09-29T13:05:00+00:00"


def _acks_text(ids, book="cef", reason="backfilled: the action predates the holding",
               rows=None, types=None):
    """ca_acks.json as the CLI writes it. Each entry's `row` is the feed row
    acknowledged: `rows[id]`, else the backfill's own row for its id, else a
    synthetic row for an id the feed does not list; `event.type` is the type
    it was listed as (`types[id]`, else the known ids' own, else name_change)."""
    rows = {"nc-ccc-backfill": BACKFILL_NC, **(rows or {})}
    types = {"nc-ccc-backfill": "name_change", "rs-ccc-acked": "reverse_split", **(types or {})}
    return json.dumps({"acks": [{"id": i, "reason": reason, "acked_utc": ACKED_AT, "book": book,
                                 "event": {"type": types.get(i, "name_change")},
                                 "row": rows.get(i, {"id": i})} for i in ids]})


def _refusal_details(state, path="cls"):
    return [r["detail"] for r in _refusals(state, path)]


def _ca_record(state, path):
    name = "send.json" if path == "late_send" else "plan.json"
    return json.loads((state / DAY / name).read_text())["corporate_actions"]


def test_the_backfill_halts_without_an_ack_and_an_acked_id_clears(tmp_path):
    """Control, then ruling B: the backfilled name change refuses every session
    on the long window; with its id acknowledged the session sends, and the
    pair is recorded under `acknowledged` with the reason, and logged. FAILS on
    4c63b1f, which reads no acknowledgement."""
    feed = _feed({"name_changes": [BACKFILL_NC]})
    c, deps, state, out, _ = _session(tmp_path / "no_ack", "cls", feed)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert any("nc-ccc-backfill" in d and "long window" in d for d in _refusal_details(state))

    c, deps, state, out, _ = _session(tmp_path / "ack", "cls", feed,
                                      acks=_acks_text(["nc-ccc-backfill"]))
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT, "".join(out)
    ca = json.loads((state / DAY / "plan.json").read_text())["corporate_actions"]
    assert ca["status"] == cam.CLEAR and ca["blocking"] == []
    assert [(a["id"], a["ack"]["reason"]) for a in ca["acknowledged"]] == [
        ("nc-ccc-backfill", "backfilled: the action predates the holding")]
    assert any("ACKNOWLEDGED, cleared for this id only" in x and "nc-ccc-backfill" in x
               for x in "".join(out).splitlines())


@pytest.mark.parametrize("path", PATHS)
def test_an_ack_clears_that_id_only_and_any_other_action_still_halts(tmp_path, path):
    """Ruling B: an ack for another id clears nothing; and with the backfill
    acknowledged, a NEW action on the same fund still refuses, naming only the
    new one. On 4c63b1f the refusal also named the acknowledged id."""
    feed = _feed({"name_changes": [BACKFILL_NC]})
    c, deps, state, out, _ = _session(tmp_path / "other", path, feed,
                                      acks=_acks_text(["some-other-id"]))
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED and c.submits() == []
    assert any("nc-ccc-backfill" in d for d in _refusal_details(state, path))

    feed = _feed({"name_changes": [BACKFILL_NC], "reverse_splits": [NEW_SPLIT_CCC]})
    c, deps, state, out, _ = _session(tmp_path / "new", path, feed,
                                      acks=_acks_text(["nc-ccc-backfill"]))
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED and c.submits() == []
    data = [d for d in _refusal_details(state, path) if "corporate-action gate" in d]
    assert len(data) == 1 and "rs-ccc-new" in data[0] and "nc-ccc-backfill" not in data[0]
    ca = _ca_record(state, path)
    assert [b["id"] for b in ca["blocking"]] == ["rs-ccc-new"]
    assert [a["id"] for a in ca["acknowledged"]] == ["nc-ccc-backfill"]


@pytest.mark.parametrize("text,why", [
    ("{not json", "JSONDecodeError"),
    (json.dumps({"acks": [{"id": "nc-ccc-backfill", "acked_utc": ACKED_AT, "book": "cef",
                           "row": BACKFILL_NC}]}), "reason None"),
    (json.dumps({"acks": [{"id": "nc-ccc-backfill", "reason": "r", "acked_utc": ACKED_AT,
                           "book": "cef", "event": {"type": "name_change"}}]}),
     "row None is not the feed row"),
    (json.dumps({"acks": [{"id": "nc-ccc-backfill", "reason": "r", "acked_utc": ACKED_AT,
                           "book": "cef", "row": BACKFILL_NC}]}),
     "does not say the action type acknowledged"),
    (_acks_text(["nc-ccc-backfill"], book="other"), "book 'other'"),
    (_acks_text(["x", "x"]), "acknowledged twice"),
    (json.dumps([]), "expected"),
    ("", "JSONDecodeError"),
], ids=["not-json", "no-reason", "no-row", "no-event-type", "other-book", "duplicate",
        "not-an-object", "empty-file"])
@pytest.mark.parametrize("path", PATHS)
def test_an_unreadable_ack_file_refuses_even_with_nothing_blocking(tmp_path, path, text, why):
    """Ruling B: a file that cannot be read is never read as empty. With a feed
    that blocks nothing, the session still REFUSES, naming the fault. On
    4c63b1f the file was ignored and the session SENT."""
    c, deps, state, out, _ = _session(tmp_path, path, _feed(), acks=text)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED and c.submits() == []
    refusals = _refusals(state, path)
    assert any(r["gate"] == "data" and "UNMEASURED" in r["detail"] and why in r["detail"]
               for r in refusals), refusals


def test_a_dangling_link_at_the_ack_path_refuses(tmp_path):
    c, deps, state, out, _ = _session(tmp_path, "cls", _feed())
    (state / cam.ACKS_FILE).symlink_to(tmp_path / "nowhere.json")
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert any("UNMEASURED" in d and "FileNotFoundError" in d for d in _refusal_details(state))


# ------------------------------------------------------- B. the ca-ack CLI

ACK_NOW = dt.datetime(2026, 9, 29, 13, 5, tzinfo=dt.timezone.utc)
REASON = "backfilled 2016 name change; paper already holds the new symbol"


def _refused_session(tmp_path, monkeypatch, feed=None):
    """A cls session the backfill refuses, so the state dir holds the gate's
    record (its names and window) for the CLI to read the feed on."""
    c, deps, state, out, _ = _session(tmp_path, "cls", feed or _feed({"name_changes":
                                                                       [BACKFILL_NC]}))
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    monkeypatch.setenv("QUANTT_STATE_DIR", str(state))
    return c, deps, state


def _ack(c, *args, now=ACK_NOW):
    return rn.ca_ack_main(["--book", "cef", *args], client=c, now=now)


def test_the_cli_acknowledges_an_id_in_the_feed_atomically_and_the_next_session_sends(
        tmp_path, monkeypatch, capsys):
    """The procedure end to end: refused -> ca-ack -> the next session sends.
    The CLI reads the feed only (no other broker call), writes through
    records.write_json_atomic, and prints what it acknowledged."""
    c, deps, state = _refused_session(tmp_path, monkeypatch)
    writes = []
    real_write = rn.rec.write_json_atomic
    monkeypatch.setattr(rn.rec, "write_json_atomic",
                        lambda p, o: writes.append(p) or real_write(p, o))
    n = len(c.calls)
    assert _ack(c, "--id", "nc-ccc-backfill", "--reason", REASON) == 0
    assert [x[0] for x in c.calls[n:]] == ["corporate_actions"]          # read-only
    assert writes == [state / cam.ACKS_FILE]
    printed = capsys.readouterr().out
    assert "ACKNOWLEDGED nc-ccc-backfill: name_change" in printed and REASON in printed
    assert "it blocked in" in printed
    acks = json.loads((state / cam.ACKS_FILE).read_text())["acks"]
    assert len(acks) == 1 and acks[0]["id"] == "nc-ccc-backfill" and acks[0]["reason"] == REASON
    assert acks[0]["acked_utc"] == ACK_NOW.isoformat() and acks[0]["book"] == "cef"
    assert acks[0]["event"]["type"] == "name_change"
    assert cam.parse_acks(json.loads((state / cam.ACKS_FILE).read_text()), "cef")
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT


def test_the_cli_refuses_an_unknown_id_and_writes_nothing(tmp_path, monkeypatch, capsys):
    c, deps, state = _refused_session(tmp_path, monkeypatch)
    assert _ack(c, "--id", "nc-ccc-typo", "--reason", REASON) == rn.EXIT_REFUSED
    assert "not in the feed" in capsys.readouterr().out
    assert not (state / cam.ACKS_FILE).exists()


def test_the_cli_refuses_a_second_ack_a_bad_reason_and_an_unreadable_file(
        tmp_path, monkeypatch, capsys):
    c, deps, state = _refused_session(tmp_path, monkeypatch)
    path = state / cam.ACKS_FILE
    assert _ack(c, "--id", "nc-ccc-backfill", "--reason", REASON) == 0
    before = path.read_bytes()
    assert _ack(c, "--id", "nc-ccc-backfill", "--reason", "again") == rn.EXIT_REFUSED
    assert "already acknowledged" in capsys.readouterr().out and path.read_bytes() == before
    for bad in ("", "   ", "two\nlines"):
        assert _ack(c, "--id", "nc-ccc-backfill", "--reason", bad) == rn.EXIT_REFUSED
    path.write_text("{not json")
    assert _ack(c, "--id", "nc-ccc-backfill", "--reason", REASON) == rn.EXIT_REFUSED
    assert path.read_text() == "{not json"                       # never rewritten as empty


def test_the_cli_refuses_without_a_gate_record_to_take_the_window_from(tmp_path, monkeypatch,
                                                                       capsys):
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("QUANTT_STATE_DIR", str(state))
    c = RealParserClient(state, feed=_feed({"name_changes": [BACKFILL_NC]}),
                         key_file=_key_file(tmp_path))
    assert _ack(c, "--id", "nc-ccc-backfill", "--reason", REASON) == rn.EXIT_REFUSED
    assert "no corporate-action record" in capsys.readouterr().out
    assert c.calls == [] and not (state / cam.ACKS_FILE).exists()


def test_a_failed_rename_leaves_the_old_file_whole(tmp_path, monkeypatch, capsys):
    """Atomic: the new file is a temp file renamed over the old one; when the
    rename fails, the old file is exactly as it was."""
    c, deps, state = _refused_session(
        tmp_path, monkeypatch, _feed({"name_changes": [BACKFILL_NC],
                                      "reverse_splits": [NEW_SPLIT_CCC]}))
    path = state / cam.ACKS_FILE
    assert _ack(c, "--id", "nc-ccc-backfill", "--reason", REASON) == 0
    before = path.read_bytes()

    def boom(src, dst):
        raise OSError("rename refused")
    monkeypatch.setattr(rn.rec.os, "replace", boom)
    assert _ack(c, "--id", "rs-ccc-new", "--reason", "corrected by hand") == rn.EXIT_FAIL
    assert "was not changed" in capsys.readouterr().out
    assert path.read_bytes() == before


def test_the_dispatcher_routes_ca_ack(monkeypatch):
    from quantt.session import __main__ as qm
    seen = []
    monkeypatch.setattr(rn, "ca_ack_main", lambda argv: seen.append(argv) or 0)
    assert qm.main(["ca-ack", "--book", "cef", "--id", "x", "--reason", "y"]) == 0
    assert seen == [["--book", "cef", "--id", "x", "--reason", "y"]]


# ---------------------- an acknowledgement holds only while the row is unchanged
#
# Release-check of 9cf5cf2 (2026-11-01): an acknowledgement cleared its id
# whatever the feed now said under it, so a revised action (another ratio, date
# or party) passed on the strength of a judgement made about a different row.
# Every test below FAILS on 9cf5cf2.

RS_ACKED = dict(OLD_SPLIT_CCC, id="rs-ccc-acked", ex_date="2026-09-25", process_date="2026-09-25")


@pytest.mark.parametrize("key,acked,revised,changed", [
    ("name_changes", BACKFILL_NC, dict(BACKFILL_NC, new_symbol="CCCX"),
     {"new_symbol": ["CCCN", "CCCX"]}),                                   # a party
    ("name_changes", BACKFILL_NC, dict(BACKFILL_NC, process_date="2026-09-25"),
     {"process_date": ["2026-09-24", "2026-09-25"]}),                     # a date
    ("reverse_splits", RS_ACKED, dict(RS_ACKED, old_rate=4),
     {"old_rate": [2, 4]}),                                               # the ratio
    ("reverse_splits", RS_ACKED, {k: v for k, v in RS_ACKED.items() if k != "cusip"},
     {"cusip": ["CCC000000", None]}),                                     # a field dropped
], ids=["party", "date", "ratio", "field-dropped"])
@pytest.mark.parametrize("path", PATHS)
def test_a_revised_row_under_an_acknowledged_id_halts_again_naming_the_change(
        tmp_path, path, key, acked, revised, changed):
    """Control first: the acknowledged row, unchanged, clears. Then the same id
    with one field revised: REFUSED, nothing sent, the refusal and the record
    (`ack_mismatch`) naming the field, its acknowledged and its current value."""
    acks = _acks_text([acked["id"]], rows={acked["id"]: acked})
    c, deps, state, out, _ = _session(tmp_path / "same", path, _feed({key: [acked]}), acks=acks)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT, "".join(out)

    c, deps, state, out, _ = _session(tmp_path / "revised", path, _feed({key: [revised]}),
                                      acks=acks)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED and c.submits() == []
    ca = _ca_record(state, path)
    assert "acknowledged" not in ca
    assert [(b["id"], b["ack_mismatch"]["changed"]) for b in ca["blocking"]] == [
        (acked["id"], changed)]
    data = [d for d in _refusal_details(state, path) if "corporate-action gate" in d]
    field, (was, now) = next(iter(changed.items()))
    assert len(data) == 1 and f"{field}: {was!r} -> {now!r}" in data[0] \
        and "the feed row has changed since" in data[0], data


def test_the_same_id_under_another_type_halts_again(tmp_path):
    """The acknowledged name change's id, now listed as a redemption of CCC."""
    redemption = {"id": BACKFILL_NC["id"], "symbol": "CCC", "cusip": "CCC000000",
                  "process_date": BACKFILL_NC["process_date"], "rate": 25.0}
    c, deps, state, out, _ = _session(tmp_path, "cls", _feed({"redemptions": [redemption]}),
                                      acks=_acks_text(["nc-ccc-backfill"]))
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    (b,) = _ca_record(state, "cls")["blocking"]
    assert b["type"] == "redemption" and "old_symbol" in b["ack_mismatch"]["changed"]


def test_the_cli_saves_the_row_and_a_revision_after_it_halts_again(tmp_path, monkeypatch,
                                                                  capsys):
    """End to end: refused -> ca-ack (which saves the feed row as listed) ->
    the next session sends -> Alpaca revises the row -> the session after
    that refuses, naming the change."""
    c, deps, state = _refused_session(tmp_path, monkeypatch)
    assert _ack(c, "--id", "nc-ccc-backfill", "--reason", REASON) == 0
    entry = json.loads((state / cam.ACKS_FILE).read_text())["acks"][0]
    assert entry["row"] == BACKFILL_NC
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    c.feed = _feed({"name_changes": [dict(BACKFILL_NC, new_symbol="CCCX")]})
    shutil.rmtree(state / DAY)                 # the next session: a fresh day dir
    c.accepted.clear()
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert any("new_symbol: 'CCCN' -> 'CCCX'" in d for d in _refusal_details(state))
    # The team lead re-judges the revised action: the same command replaces the
    # entry (the old one kept as `supersedes`) and the next session sends.
    assert _ack(c, "--id", "nc-ccc-backfill", "--reason", "revised: still stands") == 0
    (entry,) = json.loads((state / cam.ACKS_FILE).read_text())["acks"]
    assert entry["row"]["new_symbol"] == "CCCX" and entry["supersedes"]["reason"] == REASON
    assert _ack(c, "--id", "nc-ccc-backfill", "--reason", "again") == rn.EXIT_REFUSED
    shutil.rmtree(state / DAY)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT


def test_an_id_listed_with_differing_rows_is_ackable_row_by_row(tmp_path, monkeypatch, capsys):
    """Two rows under one id that read as the same event but differ in another
    field: which one is true cannot be told, so each is keyed by its content
    (`conflict`) and judged; the plain id is not acknowledgeable, each key is.
    (Until 7df8926 the CLI refused the id and the gate could never clear it.)"""
    rows = [BACKFILL_NC, dict(BACKFILL_NC, new_cusip="CCC000009")]
    c, deps, state = _refused_session(tmp_path, monkeypatch, _feed({"name_changes": rows}))
    assert _ack(c, "--id", "nc-ccc-backfill", "--reason", REASON) == rn.EXIT_REFUSED
    assert "not in the feed" in capsys.readouterr().out
    for r in rows:
        assert _ack(c, "--id", al.ca_row_key(r), "--reason", REASON) == 0
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT


# ---------------------------- unresolved rows: cleared by ca-ack, on full content
#
# docs/SYSTEM.md §5, team lead 2026-11-02 (unresolved corporate-action rows):
# the team lead clears an unresolved row with ca-ack, matched on its full raw
# content, and a revision halts again; a null id is keyed by the row's hash.
# Every test below FAILS on 709d6cb, whose read (the gate's and ca-ack's)
# raised on any such row.

def test_ca_ack_clears_an_unresolved_row_and_a_revision_halts_again(tmp_path, monkeypatch,
                                                                    capsys):
    """A held-window split with its symbol null blocks every session (long
    window, the missing subject treated as CCC). ca-ack clears it by its id and
    the next session sends; Alpaca then revises the row (the ratio), and the
    session after refuses, naming the change."""
    feed = _feed({"reverse_splits": [HELD_SPLIT_NULL_SYMBOL]})
    c, deps, state = _refused_session(tmp_path, monkeypatch, feed)
    assert _ack(c, "--id", "rs-ccc-null-symbol", "--reason", "checked: not one of ours") == 0
    printed = capsys.readouterr().out
    assert "ACKNOWLEDGED rs-ccc-null-symbol: reverse_split" in printed
    (entry,) = json.loads((state / cam.ACKS_FILE).read_text())["acks"]
    assert entry["row"] == HELD_SPLIT_NULL_SYMBOL
    assert entry["event"]["missing"] == [{"field": "symbol", "role": "subject"}]
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    ca = json.loads((state / DAY / "plan.json").read_text())["corporate_actions"]
    assert {a["id"] for a in ca["acknowledged"]} == {"rs-ccc-null-symbol"}
    c.feed = _feed({"reverse_splits": [dict(HELD_SPLIT_NULL_SYMBOL, old_rate=4)]})
    shutil.rmtree(state / DAY)
    c.accepted.clear()
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert any("old_rate: 2 -> 4" in d for d in _refusal_details(state))


def test_an_unresolved_row_with_a_null_id_is_ackable_by_its_hash(tmp_path, monkeypatch,
                                                                 capsys):
    """A null id AND a null symbol: the refusal names the row's hash key, and
    ca-ack with that key clears it; the next session sends. A revised row is a
    new key, so it halts again, unacknowledged."""
    row = dict(HELD_SPLIT_NULL_SYMBOL, id=None)
    key = al.ca_row_key(row)
    c, deps, state = _refused_session(tmp_path, monkeypatch,
                                      _feed({"reverse_splits": [row]}))
    assert any(f"ca-ack --id {key}" in d for d in _refusal_details(state))
    assert _ack(c, "--id", key, "--reason", "checked by hand") == 0
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    revised = dict(row, old_rate=4)
    c.feed = _feed({"reverse_splits": [revised]})
    shutil.rmtree(state / DAY)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert any(al.ca_row_key(revised) in d for d in _refusal_details(state))


def test_a_type_change_after_an_ack_reblocks_in_check(tmp_path):
    """The raw row carries no type (it is the list Alpaca put the row in), so
    a row moved from forward_splits to reverse_splits is unchanged byte for
    byte. The acknowledgement names the type; another type re-blocks. (The
    reviewer's probe, 2026-11-02.) On 709d6cb it cleared either type."""
    row = dict(RS_ACKED)
    acks = cam.parse_acks(json.loads(_acks_text(["rs-ccc-acked"], rows={"rs-ccc-acked": row},
                                                types={"rs-ccc-acked": "forward_split"})), "cef")
    c = RealParserClient(tmp_path / "t", feed=_feed({"forward_splits": [row]}),
                         key_file=_key_file(tmp_path))
    same = cam.check(c.corporate_actions, CLOSED, HELD, ["AAA"], ASOF, D, cam.HALT,
                     universe=SPEC["frozen"]["universe"], acks=acks)
    assert same["status"] == cam.CLEAR and [a["id"] for a in same["acknowledged"]] == [
        "rs-ccc-acked"]
    c.feed = _feed({"reverse_splits": [row]})
    moved = cam.check(c.corporate_actions, CLOSED, HELD, ["AAA"], ASOF, D, cam.HALT,
                      universe=SPEC["frozen"]["universe"], acks=acks)
    assert moved["status"] == cam.BLOCKING
    assert [b["ack_mismatch"]["changed"] for b in moved["blocking"]] == [
        {"type": ["forward_split", "reverse_split"]}]
    assert "type: 'forward_split' -> 'reverse_split'" in cam.refusal_text(moved)


def test_ca_ack_treats_a_type_change_as_a_revision(tmp_path, monkeypatch, capsys):
    """ca-ack refuses an unchanged re-acknowledgement, but the same raw row
    under another type is a revision: it is re-acknowledged (the old entry kept
    as `supersedes`) and the next session sends. On 709d6cb it refused it as
    unchanged, and the gate had cleared it anyway."""
    c, deps, state = _refused_session(tmp_path, monkeypatch,
                                      _feed({"forward_splits": [dict(RS_ACKED)]}))
    assert _ack(c, "--id", "rs-ccc-acked", "--reason", "first") == 0
    assert _ack(c, "--id", "rs-ccc-acked", "--reason", "again") == rn.EXIT_REFUSED
    assert "row and type are unchanged" in capsys.readouterr().out
    c.feed = _feed({"reverse_splits": [dict(RS_ACKED)]})
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED            # the type re-blocks
    assert _ack(c, "--id", "rs-ccc-acked", "--reason", "re-judged as a reverse split") == 0
    (entry,) = json.loads((state / cam.ACKS_FILE).read_text())["acks"]
    assert entry["event"]["type"] == "reverse_split"
    assert entry["supersedes"]["event"]["type"] == "forward_split"
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT



# ----------------- an UNDATED unresolved row (release-check of d90e68f, 2026-11-02)
#
# A null party AND an unreadable date, anywhere in the market: the read raised,
# UNMEASURED, so `halt` refused every session and ca-ack (reading the same way)
# could not clear it, and only a release could, against the ruling ("never
# needs a release to unstick"). Now it is returned undated, keyed by its hash,
# and treated as inside every window. Every test below FAILS on d90e68f.
UNDATED_OUTSIDE = dict(UNRELATED_NULL_ACQUIRER, id="sm-undated", effective_date=None)


@pytest.mark.parametrize("path", PATHS)
def test_an_undated_null_party_row_outside_the_universe_halts_naming_the_row(tmp_path, path):
    """LSI is outside the universe and the acquirer is null: with no date, the
    row cannot be shown outside any window, so it blocks (the gate's refusal,
    not UNMEASURED), naming its hash key and its unreadable date."""
    key = al.ca_row_key(UNDATED_OUTSIDE)
    c, state, log, decide_exit, code = _transmit(tmp_path, path,
                                                 _feed({"stock_mergers": [UNDATED_OUTSIDE]}))
    assert code == rn.EXIT_REFUSED and c.submits() == [], log
    data = [r["detail"] for r in _refusals(state, path) if r["gate"] == "data"]
    assert len(data) == 1 and "UNMEASURED" not in data[0], data
    assert "UNRESOLVED, UNDATED stock_merger" in data[0] and f"ca-ack --id {key}" in data[0] \
        and "'effective_date': None" in data[0], data
    (u,) = _ca_record(state, path)["unresolved"]
    assert u["id"] == key and u["blocks"] is True and u["row_id"] == "sm-undated"


def test_ca_ack_clears_an_undated_row_by_its_key_and_a_revision_halts_again(
        tmp_path, monkeypatch, capsys):
    """The way out without a release: ca-ack by the hash key the refusal
    names (matched on the full raw row); the next session sends. Alpaca then
    revises the row, still undated (another ratio): a new key, so it halts
    again until acknowledged again."""
    key = al.ca_row_key(UNDATED_OUTSIDE)
    c, deps, state = _refused_session(tmp_path, monkeypatch,
                                      _feed({"stock_mergers": [UNDATED_OUTSIDE]}))
    assert _ack(c, "--id", key, "--reason", "outside issuers; no date in the feed") == 0
    assert f"ACKNOWLEDGED {key}: stock_merger" in capsys.readouterr().out
    (entry,) = json.loads((state / cam.ACKS_FILE).read_text())["acks"]
    assert entry["row"] == UNDATED_OUTSIDE and entry["event"]["type"] == "stock_merger"
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    revised = dict(UNDATED_OUTSIDE, acquirer_rate=0.9)
    c.feed = _feed({"stock_mergers": [revised]})
    shutil.rmtree(state / DAY)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert any(al.ca_row_key(revised) in d for d in _refusal_details(state))



# ------------- a null id on a row naming ours (team lead 2026-11-02; until 7df8926 a raise)
#
# A row naming a held fund with a null, empty or non-string id raised, which
# only a release could unstick. It is keyed by its content and judged like any
# other row naming ours: it halts whenever the gate would halt for that fund,
# and ca-ack clears it on its full raw content. Every test FAILS on 7df8926.
NULL_ID_HELD_SPLIT = dict(OLD_SPLIT_CCC, id=None, ex_date="2026-09-25", process_date="2026-09-25")


@pytest.mark.parametrize("bad_id", [None, "", 7], ids=["null", "empty", "int"])
@pytest.mark.parametrize("path", PATHS)
def test_a_null_id_row_naming_a_held_fund_in_its_window_halts_naming_its_key(tmp_path, path,
                                                                            bad_id):
    row = dict(NULL_ID_HELD_SPLIT, id=bad_id)
    key = al.ca_row_key(row)
    c, state, log, decide_exit, code = _transmit(tmp_path, path,
                                                 _feed({"reverse_splits": [row]}))
    assert code == rn.EXIT_REFUSED and c.submits() == [], log
    data = [r["detail"] for r in _refusals(state, path) if r["gate"] == "data"]
    assert len(data) == 1 and "UNMEASURED" not in data[0], data
    assert f"CCC (held) is the subject in reverse_split {key}" in data[0] \
        and "it is not a usable id" in data[0] and f"ca-ack --id {key}" in data[0], data


def test_ca_ack_clears_a_null_id_row_and_a_revision_halts_again(tmp_path, monkeypatch, capsys):
    key = al.ca_row_key(NULL_ID_HELD_SPLIT)
    c, deps, state = _refused_session(tmp_path, monkeypatch,
                                      _feed({"reverse_splits": [NULL_ID_HELD_SPLIT]}))
    assert _ack(c, "--id", key, "--reason", "split confirmed on EDGAR; count fixed") == 0
    (entry,) = json.loads((state / cam.ACKS_FILE).read_text())["acks"]
    assert entry["row"] == NULL_ID_HELD_SPLIT and entry["event"]["row_id"] is None
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    revised = dict(NULL_ID_HELD_SPLIT, old_rate=4)
    c.feed = _feed({"reverse_splits": [revised]})
    shutil.rmtree(state / DAY)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED
    assert any(al.ca_row_key(revised) in d for d in _refusal_details(state))


# ------------- ca-ack and parse_acks agree on every row (execution-trader, 2026-11-02)
#
# A feed item that is not a JSON object was written by ca-ack as `"row": null`
# (or a list, a string), which parse_acks then refused, so EVERY later session
# refused and every later ca-ack too, until a hand-edit; and a NaN in a row
# never compared equal to itself, so its acknowledgement never cleared. One
# validator now (corp_actions.ack_row_canonical over alpaca.ca_row_canonical).
# Each test below FAILS on 3478159.

@pytest.mark.parametrize("item", [None, ["junk"], "not a row", 7],
                         ids=["null", "list", "string", "number"])
def test_a_non_object_feed_item_round_trips_through_ca_ack(tmp_path, monkeypatch, capsys,
                                                           item):
    """Blocks (unresolved, every party missing, undated); ca-ack writes it,
    parse_acks accepts the file, and the next session sends."""
    key = al.ca_row_key(item)
    c, deps, state = _refused_session(tmp_path, monkeypatch, _feed({"reverse_splits": [item]}))
    assert any(f"ca-ack --id {key}" in d for d in _refusal_details(state))
    assert _ack(c, "--id", key, "--reason", "a feed glitch, checked") == 0
    raw = json.loads((state / cam.ACKS_FILE).read_text())
    assert cam.parse_acks(raw, "cef")[key]["row"] == item
    assert raw["acks"][0]["row_canonical"] == al.ca_row_canonical(item)
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT


def test_a_row_with_a_nan_round_trips_and_clears(tmp_path, monkeypatch, capsys):
    """A held fund's split whose ratio is NaN: blocks (its terms cannot be
    read), ca-ack clears it, and the acknowledgement still matches when read
    back, because it is compared on the canonical text, where NaN equals NaN."""
    row = dict(OLD_SPLIT_CCC, id="rs-ccc-nan", ex_date="2026-09-25", process_date="2026-09-25",
               old_rate=float("nan"))
    c, deps, state = _refused_session(tmp_path, monkeypatch, _feed({"reverse_splits": [row]}))
    assert _ack(c, "--id", "rs-ccc-nan", "--reason", "ratio confirmed 1:2 on EDGAR") == 0
    assert "NaN" in (state / cam.ACKS_FILE).read_text()
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_SENT
    ca = json.loads((state / DAY / "plan.json").read_text())["corporate_actions"]
    assert [a["id"] for a in ca["acknowledged"]] == ["rs-ccc-nan"]


def test_parse_acks_names_the_entry_whose_canonical_form_disagrees(tmp_path):
    entry = {"id": "a1", "reason": "r", "acked_utc": ACKED_AT, "book": "cef",
             "event": {"type": "reverse_split"}, "row": ["junk"], "row_canonical": "[]"}
    with pytest.raises(ValueError, match=r"ca_acks.json acks\[0\] \(a1\): row_canonical"):
        cam.parse_acks({"acks": [entry]}, "cef")
    entry["row_canonical"] = al.ca_row_canonical(["junk"])
    assert cam.parse_acks({"acks": [entry]}, "cef")["a1"]["row"] == ["junk"]
