"""Gate 6 judges order lists read LAST, on every path that transmits.

THE DEFECT (execution-trader, release-check of 35b429f, 2026-10-29; confirmed
in code). Gate 6's Alpaca check (`gate.gate_no_set_in_auction`) is the only
guard against a second runner, or a lost state directory, doubling the book
(CLAUDE.md order-path rule 2), and `_transmit` never reads the orders again.
At 35b429f both send paths read `orders_recent` / `orders_open` near the start
and judged them only at the gate:
  * the late-market SEND (`_send_planned`): before the asset GETs, the
    closed-order history and every corporate-action page (PR #20, 7504f63);
  * the `cls` run (`run_session`, which is also the late-market DECIDE): at
    step 2, before the asset GETs, the sleeve and the corporate-action pages.
One GET that exhausts its retries takes about 250 s (docs/RUNNER.md "Latency
at the send"), and the send-budget gate refuses only past the window's end
minus the set's budget, so a stall that finished earlier sent on lists minutes
old. An order another runner placed in that gap was never seen.

THE FIX (`run._gate6_orders`). Each path reads the two lists after every other
broker read and immediately before the gate's own clock read; a failed read is
a gate-6 refusal (`gate_no_set_in_auction(..., unread=...)`), never the lists
from an earlier read and never an empty list.

THE TESTS, each shown to FAIL on 35b429f (`git archive 35b429f`, this file
copied in): 1 and 2 SENT there (the order landed after the only read), 3 SENT
there (the read it breaks came first), and 4's call-order assertion fails
there while its pins pass, because the pins were COMPUTED BY 35b429f's CODE.
  1. another runner's order lands DURING the corporate-action read: refused;
  2. ... DURING the asset GETs: refused;
  3. the read at the gate fails: refused, naming the error;
  4. nothing lands: the orders sent, send.json, plan.json, orders.jsonl,
     STARTED (bar its pid) and every run record are byte-identical to 35b429f.

HOW THE PINS WERE MADE (2026-10-29). `_outputs` run on this worktree while it
was still exactly 35b429f (clean, before run.py and gate.py were changed),
under PYTHONHASHSEED unset, 0 and 1: identical every time. Re-derive one only
after a deliberate change to what a send writes, by running `_outputs` on the
commit before that change; never edit a hash by hand.

Hermetic: test_corp_actions.CAClient (test_run.FakeClient plus the
corporate-action read), fixed clocks, state under tmp_path, the corporate-
action gate under `halt` as the deployed book sets it, no events. The second
runner's order is synthetic: it tests the code, never a claim about Alpaca.
"""
import datetime as dt
import hashlib
import json

import pytest

from quantt.broker.alpaca import AlpacaHTTPError
from quantt.session import corp_actions as cam
from quantt.session import run as rn
from quantt.session.tests.test_corp_actions import CLOSED, HELD, CAClient
from quantt.session.tests.test_run import BOOK, D, EVE, LATE, SPEC, make, to_send_time

DAY = D.isoformat()
# Another runner's set for the same auction. Same deterministic id as ours
# (`cef-<YYYYMMDD>-<SYM>-<leg>`), already FILLED: Alpaca dedupes a
# client_order_id only among ACTIVE orders [V: docs, 2026-09-28], so this is
# exactly the order whose twin Alpaca would accept and fill again.
THEIRS_FILLED = {"id": "id-other-runner", "client_order_id": "cef-20260929-AAA-1",
                 "symbol": "AAA", "side": "buy", "qty": "500", "type": "market",
                 "time_in_force": "day", "status": "filled", "filled_qty": "500",
                 "submitted_at": "2026-09-29T19:52:04Z"}
# ... and one still open (gate 6 refuses on ANY open order).
THEIRS_OPEN = {**THEIRS_FILLED, "id": "id-other-open", "client_order_id": "cef-20260929-BBB-1",
               "symbol": "BBB", "side": "sell", "status": "new", "filled_qty": "0"}
PATHS = ("late_send", "cls")


class SecondRunner(CAClient):
    """CAClient in which another runner's order lands at Alpaca DURING one of
    this session's reads, once `armed` (`during`: "corporate_actions" or
    "asset"; `into`: "recent", the status=all list, or "open").

    The fake's lists are REPLACED, never appended to, so a list this session
    read before the landing stays what it was when read, as a real response
    would. `landed_at` is the call index of the landing (the test asserts it
    happened: a test whose order never lands proves nothing)."""

    def __init__(self, state, *, during, into, **kw):
        super().__init__(state, **kw)
        self.during, self.into = during, into
        self.armed, self.landed_at = False, None

    def _land(self, where):
        if self.armed and where == self.during and self.landed_at is None:
            self.landed_at = len(self.calls)
            if self.into == "recent":
                self._recent = self._recent + [THEIRS_FILLED]
            else:
                self._open = self._open + [THEIRS_OPEN]

    def corporate_actions(self, symbols, start, end, **kw):
        got = super().corporate_actions(symbols, start, end, **kw)
        self._land("corporate_actions")
        return got

    def asset(self, sym):
        got = super().asset(sym)
        self._land("asset")
        return got


class OrdersFailAfterCA(CAClient):
    """CAClient whose `orders(status=<failing>)` read raises once `armed` and
    this session's corporate-action read has happened: the read at the gate
    fails, a read before the corporate-action block would not."""

    def __init__(self, state, *, failing, **kw):
        super().__init__(state, **kw)
        self.failing, self.armed, self.ca_done = failing, False, False

    def arm(self):
        self.armed, self.ca_done = True, False

    def corporate_actions(self, symbols, start, end, **kw):
        got = super().corporate_actions(symbols, start, end, **kw)
        self.ca_done = True
        return got

    def orders(self, *, status, after=None, **kw):
        if self.armed and self.ca_done and status == self.failing:
            self.calls.append(("orders", status, after))
            raise AlpacaHTTPError(f"GET /v2/orders failed after 5 attempts; last: HTTP 503 "
                                  f"(status={status})", status=503)
        return super().orders(status=status, after=after, **kw)


def _setup(tmp_path, path, client):
    """A session ready to transmit on `path`, CA gate under `halt`, armed.
    late_send: decided in the evening (nothing armed on the client yet), the
    clock moved to 15:53 on the session date. cls: the default 08:30 ET morning."""
    kw = {"execution": LATE, "now_utc": EVE.astimezone(dt.timezone.utc)} \
        if path == "late_send" else {}
    if path == "late_send":
        client._clock = EVE
    c, deps, state, _, out = make(tmp_path, client=client, **kw)
    deps.corp_actions = cam.HALT
    (state / "AUTO_ARMED").touch()
    if path == "late_send":
        assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_PLANNED
        assert c.submits() == []
        to_send_time(c, deps)
    return c, deps, state, out


def _refusals(state, path):
    """The refusals the transmitting run recorded: send.json for the late send,
    plan.json for cls (both always written on a refusal)."""
    name = "send.json" if path == "late_send" else "plan.json"
    return json.loads((state / DAY / name).read_text())["refusals"]


def _client(tmp_path, cls, **kw):
    return cls(tmp_path / "state", positions=HELD, closed=CLOSED, **kw)


# ---------------------------------------------- 1, 2. an order lands mid-session

@pytest.mark.parametrize("into", ["recent", "open"])
@pytest.mark.parametrize("during", ["corporate_actions", "asset"])
@pytest.mark.parametrize("path", PATHS)
def test_an_order_landing_during_the_slow_reads_refuses_the_send(tmp_path, path, during, into):
    """Tests 1 (during the corporate-action read) and 2 (during the asset GETs),
    each with the other runner's order in the status=all list (today's prefix,
    filled) and in the open list. Zero transmits, no STARTED, gate 6 names it.
    On 35b429f every case SENT: its only read came before the landing."""
    c = _client(tmp_path, SecondRunner, during=during, into=into)
    c, deps, state, out = _setup(tmp_path, path, c)
    c.armed = True
    code = rn.run_session(BOOK, SPEC, deps)
    assert c.landed_at is not None, "the other runner's order never landed: vacuous"
    assert code == rn.EXIT_REFUSED, "".join(out)
    assert c.submits() == []
    assert not (state / DAY / "STARTED").exists()
    g6 = [r["detail"] for r in _refusals(state, path) if r["gate"] == "no_set_in_auction"]
    want = ("already has order ids" if into == "recent" else "open order(s) at Alpaca")
    theirs = THEIRS_FILLED if into == "recent" else THEIRS_OPEN
    assert len(g6) == 1 and want in g6[0] and theirs["client_order_id"] in g6[0], g6


# -------------------------------------------------- 3. the read at the gate fails

@pytest.mark.parametrize("failing", ["all", "open"])
@pytest.mark.parametrize("path", PATHS)
def test_a_failed_read_at_the_gate_refuses_and_names_the_error(tmp_path, path, failing):
    """The gate's read of either list fails: a gate-6 refusal naming the error,
    zero transmits, no STARTED. Never an earlier list, never an empty one. On
    35b429f the lists were read before the corporate-action block, so this read
    never failed there and the session SENT."""
    c = _client(tmp_path, OrdersFailAfterCA, failing=failing)
    c, deps, state, out = _setup(tmp_path, path, c)
    c.arm()
    assert rn.run_session(BOOK, SPEC, deps) == rn.EXIT_REFUSED, "".join(out)
    assert c.ca_done and ("orders", failing) in [x[:2] for x in c.calls]   # it did fail
    assert c.submits() == []
    assert not (state / DAY / "STARTED").exists()
    g6 = [r["detail"] for r in _refusals(state, path) if r["gate"] == "no_set_in_auction"]
    assert len(g6) == 1, g6
    assert "could not be read" in g6[0] and "AlpacaHTTPError" in g6[0] \
        and f"status={failing}" in g6[0], g6
    assert "REFUSED [no_set_in_auction]" in "".join(out)


def test_the_gate_refuses_an_unread_list_and_still_names_started():
    """The pure gate: `unread` refuses whatever STARTED says, and a list passed
    with it (an earlier read standing in) raises rather than be judged."""
    from quantt.session import gate as gt
    got = gt.gate_no_set_in_auction(True, None, None, "cef", D, unread="X: down")
    assert [r.detail for r in got][0].startswith("STARTED exists")
    assert "could not be read" in got[1].detail and "X: down" in got[1].detail
    assert len(gt.gate_no_set_in_auction(False, None, None, "cef", D, unread="X")) == 1
    with pytest.raises(ValueError, match="unread"):
        gt.gate_no_set_in_auction(False, [], [], "cef", D, unread="X")
    with pytest.raises(ValueError, match="not read"):
        gt.gate_no_set_in_auction(False, None, [], "cef", D)


# ---------------------------------------------------- 4. nothing lands: a no-op

def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _broker_reads_before_first_submit(calls) -> list:
    """The session's broker calls up to its first POST, by kind."""
    first = next(i for i, x in enumerate(calls) if x[0] == "submit")
    return calls[:first]


def _outputs(tmp_path, path) -> tuple[dict, list]:
    """(hashes of everything the transmitting session wrote and sent, its calls).
    STARTED is hashed with `pid` removed (os.getpid differs per run)."""
    c = _client(tmp_path, CAClient)
    c, deps, state, out = _setup(tmp_path, path, c)
    n0 = len(c.calls)
    code = rn.run_session(BOOK, SPEC, deps)
    day = state / DAY
    started = json.loads((day / "STARTED").read_text())
    started.pop("pid")
    got = {"exit": code,
           "sent": _sha(json.dumps([[o["client_order_id"], o["symbol"], o["side"], o["qty"],
                                     o["time_in_force"]] for o in c.accepted.values()]).encode()),
           "plan_json": _sha((day / "plan.json").read_bytes()),
           "orders_jsonl": _sha((day / "orders.jsonl").read_bytes()),
           "started": _sha(json.dumps(started, sort_keys=True).encode()),
           "runs": {p.name: _sha(p.read_bytes()) for p in sorted((day / "runs").iterdir())}}
    if path == "late_send":
        got["send_json"] = _sha((day / "send.json").read_bytes())
    assert str(tmp_path) not in "".join(p.read_text() for p in day.rglob("*") if p.is_file()), \
        "a record holds the tmp path: the pins would not be portable"
    return got, c.calls[n0:]


# PINNED 2026-10-29 on 35b429f (module docstring: how, and how to re-derive).
PINNED_35B429F = {
    "late_send": {
        "exit": 0,
        "orders_jsonl": "f6b2e3aa52ef01e3f2576f2c28dbc938461cc54eb9fd6027747ab473fa2ffce9",
        "plan_json": "f8e800ee7f701a093ce9fe3012d6243e63c5d4295c94333dc202b7f377884477",
        "runs": {   # the evening DECIDE's record, then the SEND's
            "20260929T020000Z-run.json":
                "eb5a9bc96ff6555f7f06537b5e6a2c33ee39c08ac69559822ba6c0f84c0f5aef",
            "20260929T195300Z-run.json":
                "7b58a08a6f698836024c4cca11090b8a159ac6e8bcbc68ed65a37c29b1b39fa1"},
        "send_json": "4c40837d449ccd8ecc466c7aac0d24729c291cda3932d35c926495b73fedd921",
        "sent": "6c86cc494564dd5ccc3467b7823c14954dbaf752588fc62b092fdc8c3c797b55",
        "started": "8775070c04902f3c6e3a49827785e166271dc870ca343376fd76172ca82d0744"},
    "cls": {
        "exit": 0,
        "orders_jsonl": "7f67e3d846b0162c98d67881026cdb793f4d9cefa677bccfecc5f1acc2ef4ac7",
        "plan_json": "f5d3a0272b5dcdcc7f8ca7f55d4aff75702fc592c7b4cd392e26f8d80b35ca0d",
        "runs": {
            "20260929T123000Z-run.json":
                "1c040392958f0d1fd93703d91ab856bc912b1cc6bd594f23de593ebbac1f71de"},
        "sent": "022ad3f4f3da8d912ef0949fe203fc18a9c201a31f67e986a968015abce68a09",
        "started": "870be9690f3b555523d1195aacf47cd06044b33d0ed56b577062b4d511f078ad"},
}


def _assert_gate6_reads_last(calls):
    """The order this fix promises: each list read once; after the second of
    them, nothing reaches the broker before the first POST but the gate's clock
    read and `_transmit`'s own; every asset GET, the closed-order history and
    the corporate-action read come before them."""
    pre = _broker_reads_before_first_submit(calls)
    kinds = [x[:2] if x[0] == "orders" else x[:1] for x in pre]
    assert kinds.count(("orders", "all")) == 1 and kinds.count(("orders", "open")) == 1, kinds
    first = min(kinds.index(("orders", "all")), kinds.index(("orders", "open")))
    last = max(kinds.index(("orders", "all")), kinds.index(("orders", "open")))
    assert kinds[last + 1:] == [("clock",), ("clock",)], kinds    # the gate's, then the POST's
    slow = [i for i, k in enumerate(kinds)
            if k in (("asset",), ("corporate_actions",), ("orders", "closed"))]
    assert slow and max(slow) < first, kinds


@pytest.mark.parametrize("path", PATHS)
def test_with_nothing_landing_the_send_is_byte_identical_to_35b429f(tmp_path, path):
    """Test 4. With no other runner, everything the transmitting session wrote
    and sent equals what 35b429f's code wrote and sent (the pins), AND the lists
    were read last (`_assert_gate6_reads_last`). On 35b429f the pins match and
    the order assertion FAILS: its lists were read before every slow read."""
    got, calls = _outputs(tmp_path, path)
    assert got["exit"] == rn.EXIT_SENT and got["sent"]
    assert got == PINNED_35B429F[path], {k: (got[k], PINNED_35B429F[path].get(k))
                                         for k in got if got[k] != PINNED_35B429F[path].get(k)}
    _assert_gate6_reads_last(calls)
