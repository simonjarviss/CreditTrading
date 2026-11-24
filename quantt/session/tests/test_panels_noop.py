"""Plan row 6A is DARK: the session `default_deps` builds for today's book json is byte-identical to 862b1d0.

WHAT ROW 6A CHANGED (results/cef/C4_DEPLOY_PLAN_2026-10-27.md §1 row 6A, §2
step 5; quantt/session/run.py PER-SLEEVE PANELS). `default_deps` used to read
every close, NAV date and close history, and point the stale-NAV gate, at the
core paths `cef_discount.PX_PATH` / `NAV_PATH`; it now reads each name from the
panel its own sleeve decides on (`BookPanels`), and `sleeve_targets` takes
MarketState's prices from the sleeve's own price file. For the released book
(one sleeve, the core spec) that is the same file, read by the same call.

WHY A NEW PIN. The pins of test_combine_noop.py, test_missing_nav_hold.py and
test_c4_synthetic_pin.py drive `run_session` with deps they build themselves,
reading `cefmod.PX_PATH` directly, so they prove `run_session` and
`sleeve_targets` unchanged but never run the readers `default_deps` builds,
which are what row 6A rewired. Here the session is built BY `default_deps` from
today's book json -- late_market with bp_shortfall "scale", the stale-NAV gate
and the drawdown check in `report` -- with only what must be faked replaced
after it is built: the broker client (test_run's FakeClient), the refresh (a
fixture exit code), the halts, the clock, the log, and the stale-NAV gate's
CEFConnect reader (refusing every request, as prod's has since 2026-10-21).
The closes, NAVs, close history, targets, execution, gates and sleeves are
`default_deps`' own.

TODAY'S BOOK JSON, BOTH WAYS. `data.missing_nav = "hold"` (with
`missing_nav_max_sessions` 2) is being set by a separate change, so the book is
pinned with the key ABSENT and with it SET, each built from the released file
(`_book`): the runner-read keys of each variant are hashed into the pin's
`input`, so a later edit of the released json that changes what the runner
reads fails here, naming it, instead of passing on a book nobody pinned.

SCENARIOS (test_missing_nav_hold's, so the same branches are reached): a
complete day (the evening DECIDE, then its SEND at 15:52:30, armed) and a day
with one as-of NAV missing (the evening decide, the final check in late-market
mode, and the final check in `cls` mode, armed). Each is hashed by
test_missing_nav_hold's `_hashes`: exit, plan.json, plan_sha, orders, targets,
refusals, the run record, nav_gate.csv, send.json and what reached the broker.
With the key absent every missing-NAV day is refused; with it set, the final
check holds the fund and decides (and the cls run sends).

  * `test_synthetic_default_deps_is_5e627ff` NEVER SKIPS: test_combine_noop's
    generated 13-fund panel and fixture spec.
  * `test_real_panel_default_deps_is_5e627ff`: the live spec and a copy of the
    real panels through 2026-09-25 (test_combine_noop's input pin); it warns and
    skips when the copy or the spec is not what that pin was made on.

HOW THE PINS WERE MADE. `git archive 5e627ff` (release-20261029-2, prod's code)
into a scratch directory with the real data/ symlinked in, read only; this file
copied into that tree; `print_pins()` run there in a fresh process, unseeded
and under PYTHONHASHSEED 1; then on the row-6A tree (identical every time).
Every tmp path is replaced by `<WORK>` before hashing. To re-derive, do exactly
that again; never edit a hash by hand. This file uses only names that exist at
5e627ff for that reason; the behaviour row 6A adds is tested in
test_sleeve_panels.py.

THE CORPORATE-ACTION GATE (c4-integrate, 2026-10-29). Main (35b429f) added the
corporate-action gate after 5e627ff and set `corporate_actions.mode = "halt"` in
the released book json. 5e627ff's code (= cee16ad's, release-20261029-3, prod)
never reads that block, so the pins above are made, and checked, with it
REMOVED (`_book`, GATE_BLOCK): with the gate absent the integrated tree is
cee16ad, byte for byte. The released json AS IS -- the gate in halt, the hold
on -- is pinned separately (`RELEASED_*`, `test_*_released_book_is_35b429f`):
made on 35b429f (main, which c4-integrate was cut from) the same way, with
`git archive 35b429f` in place of 5e627ff, and the client given a feed that
lists nothing and one filled order per held name (test_c4_synthetic_pin's
`_gate_arm`), so the gate can date each held name and finds it CLEAR. Those
two pins together are the core's no-op proof for the C4 integration: the
session default_deps builds is cee16ad's with the gate absent and 35b429f's
as released.

RE-PINNED ON 862b1d0 (merge of c4-integrate onto main, 2026-11-02). Main moved
on after c4-integrate was cut: release-20261102-1 (862b1d0) is prod's code, the
released book json sets the gate to `report` (team lead 2026-11-02) and names spec
v8 in its description, and the live spec is cef_discount.v8.20261101 (CEF trial
53, `sizing_multiplier` 1.13). The 5e627ff/35b429f pins above were proofs about
book jsons and code that no longer ship, and both `book` hashes failed, as they
are built to. So BOTH families are now made on `git archive 862b1d0`, the code
the merged tree must equal for the core, the same way as before (this file
copied in, data/ symlinked read only, `print_pins` in fresh processes, unseeded
and under PYTHONHASHSEED 1; identical every time, and on c4-rel): the gate-absent
pair (`print_pins("gate_absent")`) and the released pair (`print_pins("released")`).
Two edits made that possible, and neither changes what is hashed: the clear feed
takes main's keywords (`_ClearFeedClient`), and the real-panel pins read the LIVE
spec as released, v8, against test_combine_noop's `PINNED_INPUT_V8` (the same panel
copy and v8's sha), where they used to need v7 and so skipped on every machine
since trial 53. The 5e627ff and 35b429f pins are in git at 8b001c9.

SINCE CEF TRIAL 53 AMENDMENT 1 (2026-11-02) the live spec is v9 (x1.30). The 862b1d0
pins are unchanged, byte for byte. Their real-panel pair now reads v8 from git at
862b1d0 (`test_combine_noop.v8_spec`, `_v8_input`) instead of the live file, so they
still run. The book json still names the live spec's path, as when they were made.

THE BOOK'S PROSE IS NOT HASHED (release-check of 336df9d, QR3, 2026-11-03). `_runner_keys`
drops the top-level `description` too (PROSE_KEYS): no code reads it, and the core's named
v8 x1.13 after v9 x1.30 shipped. Correcting it changed only the six `book` hashes, which
were re-derived the same way (`git archive 862b1d0`, this file and f27ef81's
test_combine_noop.py copied in, the corrected book json copied in, GIT_DIR at the dev repo
so `v8_spec` reads 862b1d0 from git; unseeded and under PYTHONHASHSEED 1, identical): every
other entry of every pin regenerated byte for byte.

Hermetic: no network (netguard; the CEFConnect reader raises), no key file (the
client factory is faked), state under tmp_path, the real panels read only.
"""
import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

from quantt.session import run as rn
from quantt.session.tests.test_combine_noop import (
    LIVE_SPEC_PATH,
    PINNED_INPUT_V8 as COMBINE_PINNED_INPUT,
    v8_spec,
    SYN_SPEC,
    RealPanelPinNotApplicable,
    _client,
    _frozen_copy,
    _real_panel_ready,
    _write_synthetic,
)
from quantt.session.tests.test_run import FakeClient
from quantt.session.tests.test_missing_nav_hold import (
    ASOF,
    CLS_SCALE,
    EVE,
    FINAL,
    HOLD,
    MAX_SESSIONS,
    REAL_MISSING,
    SEND,
    SESSION,
    SYN_MISSING,
    _Quiet,
    _hashes,
    _held_book,
    _prior_plan,
    _refused,
    _scenario_panel,
    _write_priors,
)

MISSING_NAV_KEYS = ("missing_nav", "missing_nav_max_sessions", "_missing_nav_note")
GATE_BLOCK = "corporate_actions"     # main's gate (module docstring); 5e627ff never reads it


def _sha(b) -> str:
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


# Top-level prose no code reads (checked 2026-11-03: nothing in quantt/, ops/ or scripts/
# reads a book json's `description`). Hashing it made a correction of the prose (QR3 of the
# release-check of 336df9d: the core's description named v8 x1.13 after v9 x1.30 shipped)
# look like a change to what the runner reads.
PROSE_KEYS = ("description",)


def _runner_keys(book: dict) -> dict:
    """The book json as the runner reads it: every block, notes (`_` keys) and the top-level
    prose (PROSE_KEYS) dropped."""
    def strip(v):
        if isinstance(v, dict):
            return {k: strip(x) for k, x in v.items() if not k.startswith("_")}
        if isinstance(v, list):
            return [strip(x) for x in v]
        return v
    return {k: v for k, v in strip(book).items() if k not in PROSE_KEYS}


def _book(work: Path, spec_path: Path, key: bool, *, released: bool = False) -> tuple:
    """(Book, sha of its runner-read keys): the released book json with the
    missing-NAV keys removed (`key` False) or set to the team lead's values
    (True), its one sleeve naming `spec_path`. A spec outside the repository is
    named by its absolute path, which `combine.load_sleeves` resolves as itself.

    The corporate-action gate's block is removed too (module docstring, THE
    CORPORATE-ACTION GATE), unless `released`: then the json is exactly as
    released, gate and hold included, and `key` must say the hold is on."""
    book = json.loads(rn.BOOKS["cef"].book_path.read_text())
    if released:
        assert key and (book.get("data") or {}).get("missing_nav") == HOLD, book.get("data")
        data = dict(book.get("data") or {})
    else:
        book.pop(GATE_BLOCK, None)
        data = {k: v for k, v in (book.get("data") or {}).items() if k not in MISSING_NAV_KEYS}
        if key:
            data.update(missing_nav=HOLD, missing_nav_max_sessions=MAX_SESSIONS)
    book["data"] = data
    assert len(book["sleeves"]) == 1, book["sleeves"]
    try:
        sp = spec_path.relative_to(rn.REPO).as_posix()
        shown = sp
    except ValueError:
        sp, shown = str(spec_path), "<SPEC>"
    book["sleeves"] = [dict(book["sleeves"][0], spec_path=sp)]
    path = work / ("book_released.json" if released else
                   "book_hold.json" if key else "book_absent.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(book, indent=1))
    pinned = _runner_keys(book)
    pinned["sleeves"] = [dict(pinned["sleeves"][0], spec_path=shown)]
    return (rn.Book("cef", "cef", spec_path, path),
            _sha(json.dumps(pinned, sort_keys=True)))


class _ClearFeedClient(FakeClient):
    """test_run's FakeClient with Alpaca's corporate-action read, listing nothing
    (test_c4_synthetic_pin's _ClearFeed): the released book's gate reads it."""
    def corporate_actions(self, symbols, start, end, **kw):
        # **kw: main's gate passes `universe` and `skipped` (corp_actions.check,
        # a40170c); an empty feed has nothing to skip or record.
        self.calls.append(("corporate_actions", tuple(sorted(symbols)), start, end))
        return []


def _gate_client(state, held, closes, clock_ts):
    """test_combine_noop's `_client`, plus the feed above and one filled order per
    held name (test_c4_synthetic_pin's `_gate_arm`), so the gate dates each one."""
    closed = [{"id": f"fill-{s}", "client_order_id": f"cef-20260902-{s}-1", "symbol": s,
               "side": "buy" if q > 0 else "sell", "status": "filled",
               "filled_qty": str(abs(q)), "submitted_at": "2026-09-01T19:52:00Z"}
              for s, q in sorted(held.items())]
    c = _ClearFeedClient(state, positions=held, closed=closed, clock_ts=clock_ts)
    c.long_mv = sum(q * closes[s] for s, q in held.items() if q > 0)
    c.short_mv = sum(q * closes[s] for s, q in held.items() if q < 0)
    c.maint = 0.5 * (c.long_mv - c.short_mv)                 # fixture, not a measurement
    return c


def _session(work: Path, book, spec, held, now, mp, *, refresh_exit, key: bool,
             execution=None, armed=False, gate=False):
    """One run_session on deps built by `default_deps(book, spec, env)`, with
    only the fakes the module docstring names replaced after it is built.
    `gate`: the released book, whose corporate-action gate reads the clear feed."""
    from ops.schedule.nyse_calendar import previous_trading_day
    from quantt.broker import alpaca
    from src.deploy.sleeves import cef_discount as cefmod
    p = rn.spec_params(spec)
    state = work / "state"
    state.mkdir(parents=True, exist_ok=True)
    if key:
        # The previous session's record, every NAV dated: the age limit's count is 0.
        prev = previous_trading_day(SESSION)
        _write_priors(state, {prev: _prior_plan(prev)})
    if armed:
        (state / "AUTO_ARMED").touch()
    closes = {s: v[0] for s, v in rn.last_closes(cefmod.PX_PATH, ASOF, p["universe"]).items()}
    c = (_gate_client if gate else _client)(state, held, closes, now)
    mp.setattr(alpaca.AlpacaClient, "from_environment",
               classmethod(lambda cls, name, **kw: c))
    deps = rn.default_deps(book, spec, {"QUANTT_ENV_FILE": "unused"})
    assert deps.client is c and deps.sleeves is None
    assert (deps.missing_nav == HOLD) is key
    deps.env = {"QUANTT_STATE_DIR": str(state), "DRY_RUN": "0"}
    deps.refresh = lambda a, t: rn.RefreshResult(exit=refresh_exit, tail="fixture")
    deps.halts = lambda: []
    deps.utcnow = lambda: now.astimezone(dt.timezone.utc)
    deps.out = _Quiet()
    deps.nav_gate.reader = _refused
    if execution is not None:
        deps.execution = execution
    code = rn.run_session(book, spec, deps)
    return code, state, c


def _scenarios(work: Path, base: Path, mp, spec, spec_path: Path, missing: str,
               key: bool, *, released: bool = False) -> dict:
    book, book_sha = _book(work, spec_path, key, released=released)
    g = {"gate": released}
    out = {"book": book_sha}
    _scenario_panel(base, work / "complete" / "panel", mp, ASOF)
    held = _held_book(spec, ASOF, rn.spec_params(spec)["capital_usd"])
    w = work / "complete"
    code, state, c = _session(w, book, spec, held, EVE, mp, refresh_exit=0, key=key, **g)
    out["complete|decide"] = _hashes(w, state, code, c)
    code, state, c = _session(w, book, spec, held, SEND, mp, refresh_exit=0, key=key,
                              armed=True, **g)
    out["complete|send"] = _hashes(w, state, code, c, send=True)
    for label, now, ex, armed in (("eve", EVE, None, False), ("final", FINAL, None, False),
                                  ("final_cls", FINAL, CLS_SCALE, True)):
        w = work / f"missing_{label}"
        _scenario_panel(base, w / "panel", mp, ASOF, nav=(missing,))
        code, state, c = _session(w, book, spec, held, now, mp, refresh_exit=4, key=key,
                                  execution=ex, armed=armed, **g)
        out[f"missing|{label}"] = _hashes(w, state, code, c)
    return out


def _synthetic_pins(work: Path, mp) -> dict:
    base = work / "base"
    base.mkdir(parents=True)
    _, _, _, panel_sha = _write_synthetic(base)
    spec_path = work / "synthetic.frozen.json"
    spec_path.write_text(json.dumps(SYN_SPEC))
    out = {"panel": panel_sha}
    for name, key in (("absent", False), ("hold", True)):
        out[name] = _scenarios(work / name, base, mp, SYN_SPEC, spec_path, SYN_MISSING, key)
    return out


def _v8_input(work: Path, mp):
    """(spec, input) for the 862b1d0 pins: the core's spec as released at 862b1d0 (v8), read from
    git (test_combine_noop.v8_spec), since the live spec moved to v9 (CEF trial 53 amendment 1). The
    book still names LIVE_SPEC_PATH, as when the pins were made. Nothing in the session reads that
    file's content (the spec dict is passed in), so the book's runner-read keys and every output
    are the same bytes. (None, None) when git cannot show it."""
    v8 = v8_spec()
    if v8 is None:
        return None, None
    raw, spec = v8
    base = work / "base"
    base.mkdir(parents=True)
    return spec, {"panel": _frozen_copy(base, mp, spec["frozen"]["universe"]), "spec": _sha(raw)}


def _real_pins(work: Path, mp) -> dict | None:
    """None when git cannot show v8, or the real copy or v8 is not what the pin was made on."""
    spec, got = _v8_input(work, mp)
    base = work / "base"
    if got != COMBINE_PINNED_INPUT:
        return None
    return {name: _scenarios(work / name, base, mp, spec, LIVE_SPEC_PATH, REAL_MISSING, key)
            for name, key in (("absent", False), ("hold", True))}


def _released_synthetic_pins(work: Path, mp) -> dict:
    """The released book json as is, on the synthetic panel (module docstring,
    THE CORPORATE-ACTION GATE)."""
    base = work / "base"
    base.mkdir(parents=True)
    _, _, _, panel_sha = _write_synthetic(base)
    spec_path = work / "synthetic.frozen.json"
    spec_path.write_text(json.dumps(SYN_SPEC))
    return {"panel": panel_sha,
            "released": _scenarios(work / "released", base, mp, SYN_SPEC, spec_path,
                                   SYN_MISSING, True, released=True)}


def _released_real_pins(work: Path, mp) -> dict | None:
    spec, got = _v8_input(work, mp)
    base = work / "base"
    if got != COMBINE_PINNED_INPUT:
        return None
    return {"released": _scenarios(work / "released", base, mp, spec, LIVE_SPEC_PATH,
                                   REAL_MISSING, True, released=True)}


def print_pins(which: str = "gate_absent"):
    """Print the pins (module docstring, RE-PINNED ON 862b1d0): `gate_absent` the
    gate-absent pair, `released` the released book's pair. Run in a `git archive`
    of the reference commit with this file copied in, never on the tree tested."""
    import tempfile
    if which not in ("gate_absent", "released"):
        raise ValueError(f"which={which!r}: 'gate_absent' or 'released'")
    fns = ({"SYN_PINNED": _synthetic_pins, "REAL_PINNED": _real_pins} if which == "gate_absent"
           else {"RELEASED_SYN_PINNED": _released_synthetic_pins,
                 "RELEASED_REAL_PINNED": _released_real_pins})
    for name, fn in fns.items():
        with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
            print(name, "=", json.dumps(fn(Path(d) / "w", mp), indent=1, sort_keys=True))


# PINNED 2026-11-02 on 862b1d0 (release-20261102-1, main), the gate block removed:
# `print_pins("gate_absent")` in a `git archive 862b1d0` tree, unseeded and under
# PYTHONHASHSEED 1 (identical); module docstring, RE-PINNED ON 862b1d0. Until then
# made on 5e627ff (in git at 8b001c9).
SYN_PINNED = {
 "absent": {
  "book": "4dc0d597827fd8d20555e8a73540a6b2f7c9cf5d9cef1c7bbc1dfa9cb2ec52ec",
  "complete|decide": {
   "exit": 6,
   "n_orders": 7,
   "nav_gate_csv": "a43fad90c4741dc4b1cc9cef3f7eb697a360c4779d3ac981ee8df218e287a845",
   "orders": "e628eb451ee60ed44c2a3432437a51e54f7759a97439d112ce119d11e3271024",
   "plan_json": "6d81b758b730f5c5901cc307decf1f6ea354da71d7cc3dd0b0f4c181d8835368",
   "plan_sha": "aa3cc8b1827344eac6a143892be4faa969df5bcb1431b09903b93b8c229a780e",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "fef25235298115511f49fb9e859527400d2f4e51f24338506c2c0e7032cd2779",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "decided",
   "targets": "732894a285fe4821a443ae4ce9d9d609cc3e382edc831ccb239c03e155f5fb6f"
  },
  "complete|send": {
   "exit": 0,
   "run_record": "2ba2408c6f4f2039f65594d86948e8d88ef22afaf654b6d118f60f35dc3babee",
   "send_json": "28900ab87d89f8716cc885b35b3612f9f9b33ca0be117b85d12659cbd5624819",
   "sent": "5409c95d63e197ab80437a44fa71fb69e234f2578348b84b75cc9217193f6aaf"
  },
  "missing|eve": {
   "exit": 11,
   "n_orders": 0,
   "nav_gate_csv": None,
   "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "plan_json": "eac2080f6b0e3099dd1b535da8d0434a75d3717f32da5f61e1a314629bd5f7b6",
   "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "refusals": "630bfc011cbaf9c3a07f35493598a808548ddb9c617fbcb8e42f2a19bc5d25ed",
   "run_record": "676630c02f863db9e92089d8e63f55171e62b598acbdd6b5bf9600d67a900c98",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "refused",
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
  },
  "missing|final": {
   "exit": 11,
   "n_orders": 0,
   "nav_gate_csv": None,
   "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "plan_json": "eac2080f6b0e3099dd1b535da8d0434a75d3717f32da5f61e1a314629bd5f7b6",
   "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "refusals": "630bfc011cbaf9c3a07f35493598a808548ddb9c617fbcb8e42f2a19bc5d25ed",
   "run_record": "f241e3222dc6c112b0cb1bedab8baf0b9988505404d6a991ec969a7979c38b83",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "refused",
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
  },
  "missing|final_cls": {
   "exit": 11,
   "n_orders": 0,
   "nav_gate_csv": None,
   "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "plan_json": "9edca0afad5cacdaed81517f4048bf86c3a39ccfb7f595c5f2f1b75cccc9fdc5",
   "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "refusals": "630bfc011cbaf9c3a07f35493598a808548ddb9c617fbcb8e42f2a19bc5d25ed",
   "run_record": "1f4caf668b2f85cc257816187e5cc00bafb93538350a5f7b942b7357926d4066",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": None,
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
  }
 },
 "hold": {
  "book": "d7266352e3353af8991a7b3861d6d61a8633464acd310cec15b4f578910fe49b",
  "complete|decide": {
   "exit": 6,
   "n_orders": 7,
   "nav_gate_csv": "a43fad90c4741dc4b1cc9cef3f7eb697a360c4779d3ac981ee8df218e287a845",
   "orders": "e628eb451ee60ed44c2a3432437a51e54f7759a97439d112ce119d11e3271024",
   "plan_json": "8a419869b91ed92c14e6bbc1b4881fdf00ab64b5f599626abfba35f28f5ae720",
   "plan_sha": "aa3cc8b1827344eac6a143892be4faa969df5bcb1431b09903b93b8c229a780e",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "ce6efea304c72a4585826377403a017b11fe37f465e1bde7aac4a52d9bcb07cf",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "decided",
   "targets": "732894a285fe4821a443ae4ce9d9d609cc3e382edc831ccb239c03e155f5fb6f"
  },
  "complete|send": {
   "exit": 0,
   "run_record": "2ba2408c6f4f2039f65594d86948e8d88ef22afaf654b6d118f60f35dc3babee",
   "send_json": "28900ab87d89f8716cc885b35b3612f9f9b33ca0be117b85d12659cbd5624819",
   "sent": "5409c95d63e197ab80437a44fa71fb69e234f2578348b84b75cc9217193f6aaf"
  },
  "missing|eve": {
   "exit": 11,
   "n_orders": 0,
   "nav_gate_csv": "a43fad90c4741dc4b1cc9cef3f7eb697a360c4779d3ac981ee8df218e287a845",
   "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "plan_json": "13a0b7b2b75614aa4d6eb3841d666ab2312641b4147df66a06c955942603cedf",
   "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "refusals": "0d32802d42ce7301e6a64fd20245a41f44cf43cb6831cad8175bff9375748d66",
   "run_record": "80c8df9a59d20ef25fb9bfc081be216b07cee5929c5ee328260f7fdadfcd50c0",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "refused",
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
  },
  "missing|final": {
   "exit": 6,
   "n_orders": 6,
   "nav_gate_csv": "8c5ca313d8bddeb168b5f6b56f8f909f90e67576f2309c9dde7157d758097d86",
   "orders": "8e83a5fab26db52c76fcfbc357e9d9674bb742cca88049155b4f2a64e7f63d9a",
   "plan_json": "e7df59e91474884e49aa3ed87e4a752cfc4f021a286b19bafbf98280a4cb40a2",
   "plan_sha": "dabc5f382dc87baecf74fe4782e0c5f07902dc744eb7c5ae8bf5e0e59cdcb500",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "8ae2bf7126afc593fa4bfda3113196f6867722a38222efdc07f296cad6204103",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "decided",
   "targets": "ad3fafebc78bba0add3d0f9c46c1c629d3d30a6e15a852a9cc04ed8594c0f9c0"
  },
  "missing|final_cls": {
   "exit": 0,
   "n_orders": 6,
   "nav_gate_csv": "8c5ca313d8bddeb168b5f6b56f8f909f90e67576f2309c9dde7157d758097d86",
   "orders": "97bb764435fad43e59e6fe5be9480eccf28231974fd49bc8555bbdba79fa5a88",
   "plan_json": "c1d1366fbafbaa92c94f52a7e4840ee628a60b08eff9f6674132c35a776e1bf3",
   "plan_sha": "11b246acc248978f8cfb0e8f0d9ba58b4cead022b23bfa9284e31de4d7db92cb",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "9191f3f986c4831a2ea07cc2d33e4219df0ec8ec2fb5047ae00073719eece36f",
   "sent": "178635e34eccb5810101fda355a3f703e6f4f17a7bef24cee399e3a9e60afbc5",
   "status": None,
   "targets": "ad3fafebc78bba0add3d0f9c46c1c629d3d30a6e15a852a9cc04ed8594c0f9c0"
  }
 },
 "panel": "172d57548229a8776518927875787e15e3c5476f9e57cd9df99e90c78738b277"
}
# PINNED 2026-11-02 on 862b1d0, the gate block removed, on the laptop's dev panels
# (cef_prices to 2026-10-15; only rows through 2026-09-25 are read) and the live spec v8
# (test_combine_noop's PINNED_INPUT_V8). Until then made on 5e627ff with v7.
REAL_PINNED = {
 "absent": {
  "book": "c1b57dd3bc19ce17545725e3ecd31398be4077449c83fcf884d01b8b61b7aa13",
  "complete|decide": {
   "exit": 6,
   "n_orders": 6,
   "nav_gate_csv": "18734cfdbe33cc779a2277bef135248fcafa1c90de9b2a0c203ae82a729af304",
   "orders": "037bdf2b328be4ea86d1c6b581918fc8219d9f2e8a58e2d6da31edf1f0794830",
   "plan_json": "991d914652f1979f8aac2320a5c7d256c81160fc1eb51a2e533cee759901a41e",
   "plan_sha": "03509da3b3be0cc129fb1029116a58dac5a1ef26c90fb6590216d2b8ce3eebc7",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "e6fdf113663edd8b6a0211cc79acbdd047f800cecfddbe6d670069132f6cb134",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "decided",
   "targets": "a18254b6c48fd1c58d2c45eb84ea766c8f3df55368f6520ab4d9cf055ef34369"
  },
  "complete|send": {
   "exit": 0,
   "run_record": "6746d7f7d948500b0ca6785a2f27f5ded6738e6075115fc40d7ea6770573af23",
   "send_json": "9829d3c1a7c04b1596dec5f6aa8924273f02443bab9b918f19ba6a6e56552834",
   "sent": "8aaa3cd32318320fe85ad32276dbdb7c144fecbda9370e7e7d319ef50a666a50"
  },
  "missing|eve": {
   "exit": 11,
   "n_orders": 0,
   "nav_gate_csv": None,
   "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "plan_json": "9e9d2be31ed25f4473ca903c8c15b310dd2eaaa7c3e3a8be745d825771d62fda",
   "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "refusals": "0bd11e7d2acb6a4d1333ffa81814bd978c4247336c94639a7005ddcefcb9a865",
   "run_record": "6a86132b45401cb883bba86490409ff4044e94fa360dad710718be269163b428",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "refused",
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
  },
  "missing|final": {
   "exit": 11,
   "n_orders": 0,
   "nav_gate_csv": None,
   "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "plan_json": "9e9d2be31ed25f4473ca903c8c15b310dd2eaaa7c3e3a8be745d825771d62fda",
   "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "refusals": "0bd11e7d2acb6a4d1333ffa81814bd978c4247336c94639a7005ddcefcb9a865",
   "run_record": "530bb0921eb51791a32f60289cfaf8e0eb2ce725e71c271d2cbb320a86763d11",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "refused",
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
  },
  "missing|final_cls": {
   "exit": 11,
   "n_orders": 0,
   "nav_gate_csv": None,
   "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "plan_json": "af85cb16502c451cd708fd88bafa66657847e0a9b9f2579471bdd0e8a0bbea5e",
   "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "refusals": "0bd11e7d2acb6a4d1333ffa81814bd978c4247336c94639a7005ddcefcb9a865",
   "run_record": "2ef3c0d65960601bd0c482223327cec36a06fe05cfe629798a7b548f26667f6b",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": None,
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
  }
 },
 "hold": {
  "book": "07fd6aa19f3e1d79c0346513861955bbc7390dda1c611f4ce73293f4453d4bdd",
  "complete|decide": {
   "exit": 6,
   "n_orders": 6,
   "nav_gate_csv": "18734cfdbe33cc779a2277bef135248fcafa1c90de9b2a0c203ae82a729af304",
   "orders": "037bdf2b328be4ea86d1c6b581918fc8219d9f2e8a58e2d6da31edf1f0794830",
   "plan_json": "0dea67e8b4670266699994bd0d507ca0455a963d6e0078138dd385573c48d290",
   "plan_sha": "03509da3b3be0cc129fb1029116a58dac5a1ef26c90fb6590216d2b8ce3eebc7",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "b0d49c1f8731863e1078a6e3742583e3cf17c550185a863a03b6422ad95d3ada",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "decided",
   "targets": "a18254b6c48fd1c58d2c45eb84ea766c8f3df55368f6520ab4d9cf055ef34369"
  },
  "complete|send": {
   "exit": 0,
   "run_record": "6746d7f7d948500b0ca6785a2f27f5ded6738e6075115fc40d7ea6770573af23",
   "send_json": "9829d3c1a7c04b1596dec5f6aa8924273f02443bab9b918f19ba6a6e56552834",
   "sent": "8aaa3cd32318320fe85ad32276dbdb7c144fecbda9370e7e7d319ef50a666a50"
  },
  "missing|eve": {
   "exit": 11,
   "n_orders": 0,
   "nav_gate_csv": "18734cfdbe33cc779a2277bef135248fcafa1c90de9b2a0c203ae82a729af304",
   "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "plan_json": "0ebac7bd4b0c739aa43265ecff3079d13a31be3d2463dd8e6abe6940e1b27761",
   "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "refusals": "45fb724cc5c4f4b809d81561866376313a6deee1633f27933aef93a6c4e09b03",
   "run_record": "c68b4f26a8866838d7d23191473ee37adabc946c9777003b61c7db4881705519",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "refused",
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
  },
  "missing|final": {
   "exit": 6,
   "n_orders": 5,
   "nav_gate_csv": "3e17b6fc3741ec740818874935a3a078f2b300f7ee49a86dd1204828f1597100",
   "orders": "9b7f367c05673eb6e51a7617ca8c1e3df33a1ac8b670a8d0b2b3e41904843b07",
   "plan_json": "98416e6bc5c8f40e095955695b612daad219483556fed542fc126aa67aa2e040",
   "plan_sha": "424ed40c4df4bf5ad166484b392ab1062cc948ad894722444930904bdf534a82",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "f7bfc0f210a784739fb8ecfa9eb7fac8b2ff388b4611dbd16da4ac4c49da2c93",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "decided",
   "targets": "5b9f106426de44eaeb18641a86c3f53452d223ae4fc466df6df9970d7dbc2036"
  },
  "missing|final_cls": {
   "exit": 0,
   "n_orders": 5,
   "nav_gate_csv": "3e17b6fc3741ec740818874935a3a078f2b300f7ee49a86dd1204828f1597100",
   "orders": "71adff005d8e0ea1f5f46af244f5d3b547961dacc8c0a0c2a091ec089f6f1e67",
   "plan_json": "95270a2dcf88e121e2b8d4f5f56102ccd2659ea7f2f204a7264b994f052185d0",
   "plan_sha": "f6095fcfa894c6253137a628d3d00190547065d3c51db6634ce0c33c80e2caee",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "cbb83246aa73d4b353c282a70ed2c78947b33672400665a29d06cd46c1535d32",
   "sent": "6f7bccd5afbf21a8e7298cff39b9c1e238f3252e6a6da0c56204624bb01dfc85",
   "status": None,
   "targets": "5b9f106426de44eaeb18641a86c3f53452d223ae4fc466df6df9970d7dbc2036"
  }
 }
}


# PINNED 2026-11-02 on 862b1d0 (release-20261102-1, main): the released book json as
# is, the corporate-action gate in REPORT (team lead 2026-11-02) against a clear feed
# (module docstring, THE CORPORATE-ACTION GATE). `print_pins("released")` in a
# `git archive 862b1d0` tree, unseeded and under PYTHONHASHSEED 1 (identical), then on
# c4-rel (identical again). Until then made on 35b429f with the gate in halt.
RELEASED_SYN_PINNED = {
 "panel": "172d57548229a8776518927875787e15e3c5476f9e57cd9df99e90c78738b277",
 "released": {
  "book": "2a942f2b83f054600ef2b642c9d82107d7c94bbf09d5bfd20371c65410113d6a",
  "complete|decide": {
   "exit": 6,
   "n_orders": 7,
   "nav_gate_csv": "a43fad90c4741dc4b1cc9cef3f7eb697a360c4779d3ac981ee8df218e287a845",
   "orders": "e628eb451ee60ed44c2a3432437a51e54f7759a97439d112ce119d11e3271024",
   "plan_json": "8451da694905286c408bd0edb65c7114dc55dffcbe863b207ca0ac0207201352",
   "plan_sha": "aa3cc8b1827344eac6a143892be4faa969df5bcb1431b09903b93b8c229a780e",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "dc6b959a8ec8dd31ac59491aa0e0e974542a5cd72fb8d8e6a55d11b1ce140315",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "decided",
   "targets": "732894a285fe4821a443ae4ce9d9d609cc3e382edc831ccb239c03e155f5fb6f"
  },
  "complete|send": {
   "exit": 0,
   "run_record": "87395a39cab28cd27326eaa2f773684d2499459c0cc2e1d1aaf89ea3298d017d",
   "send_json": "c8247f662bb788c21d1bf1701a4641330bf23679d05a0b4e106b8403eb5dc05b",
   "sent": "5409c95d63e197ab80437a44fa71fb69e234f2578348b84b75cc9217193f6aaf"
  },
  "missing|eve": {
   "exit": 11,
   "n_orders": 0,
   "nav_gate_csv": "a43fad90c4741dc4b1cc9cef3f7eb697a360c4779d3ac981ee8df218e287a845",
   "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "plan_json": "2510ad85d2f6fc70341c47fbce077bb02511a86718f8761ceace41d7d03cc3f6",
   "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "refusals": "0d32802d42ce7301e6a64fd20245a41f44cf43cb6831cad8175bff9375748d66",
   "run_record": "638d3b0a452032271b710e277e7943acb496d67ffc734a15e974bfb7049fc5ee",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "refused",
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
  },
  "missing|final": {
   "exit": 6,
   "n_orders": 6,
   "nav_gate_csv": "8c5ca313d8bddeb168b5f6b56f8f909f90e67576f2309c9dde7157d758097d86",
   "orders": "8e83a5fab26db52c76fcfbc357e9d9674bb742cca88049155b4f2a64e7f63d9a",
   "plan_json": "05ae1230eee06a990adf7e07418a1617b20811054710878d7207f1542a33b7d1",
   "plan_sha": "dabc5f382dc87baecf74fe4782e0c5f07902dc744eb7c5ae8bf5e0e59cdcb500",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "8bffa8cc96573dc32871f0987aca903e8ba8398a23f1a6737410551ddc0ded21",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "decided",
   "targets": "ad3fafebc78bba0add3d0f9c46c1c629d3d30a6e15a852a9cc04ed8594c0f9c0"
  },
  "missing|final_cls": {
   "exit": 0,
   "n_orders": 6,
   "nav_gate_csv": "8c5ca313d8bddeb168b5f6b56f8f909f90e67576f2309c9dde7157d758097d86",
   "orders": "97bb764435fad43e59e6fe5be9480eccf28231974fd49bc8555bbdba79fa5a88",
   "plan_json": "1e531bae16ad7ec1edd3233d6b5c6a183192e735a9caaa3b6e4c3d30c18b964d",
   "plan_sha": "11b246acc248978f8cfb0e8f0d9ba58b4cead022b23bfa9284e31de4d7db92cb",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "e32815e98847c81e5bc7c194bdd5400bbb45bd1fc32f2042ded5e9673e5db8c9",
   "sent": "178635e34eccb5810101fda355a3f703e6f4f17a7bef24cee399e3a9e60afbc5",
   "status": None,
   "targets": "ad3fafebc78bba0add3d0f9c46c1c629d3d30a6e15a852a9cc04ed8594c0f9c0"
  }
 }
}
# PINNED 2026-11-02 on 862b1d0, on the laptop's dev panels and the live spec v8
# (test_combine_noop's PINNED_INPUT_V8). Until then made on 35b429f with v7.
RELEASED_REAL_PINNED = {
 "released": {
  "book": "f40cb49aa6c380b6d1950575f74516165030a99eee5eeb5e0718a96662227b3c",
  "complete|decide": {
   "exit": 6,
   "n_orders": 6,
   "nav_gate_csv": "18734cfdbe33cc779a2277bef135248fcafa1c90de9b2a0c203ae82a729af304",
   "orders": "037bdf2b328be4ea86d1c6b581918fc8219d9f2e8a58e2d6da31edf1f0794830",
   "plan_json": "771a3fd00558ee44f066dd5e4e8a191348397ed05efe05428dcce505f476e71e",
   "plan_sha": "03509da3b3be0cc129fb1029116a58dac5a1ef26c90fb6590216d2b8ce3eebc7",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "ec6e656060a47b26e15d5d63dd4b6ecff468e4d16dd4549115248d7db061bee0",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "decided",
   "targets": "a18254b6c48fd1c58d2c45eb84ea766c8f3df55368f6520ab4d9cf055ef34369"
  },
  "complete|send": {
   "exit": 0,
   "run_record": "4d8e558a97fab4b2df5afd7bd18e1359969722a4ffa6d72388770cb2be5be8d7",
   "send_json": "4c6221e465ef1f44e839b4d51d807ec6f5de8eb8717bf172c17ec92b06676af7",
   "sent": "8aaa3cd32318320fe85ad32276dbdb7c144fecbda9370e7e7d319ef50a666a50"
  },
  "missing|eve": {
   "exit": 11,
   "n_orders": 0,
   "nav_gate_csv": "18734cfdbe33cc779a2277bef135248fcafa1c90de9b2a0c203ae82a729af304",
   "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "plan_json": "02515ffc4fd4e42db85691605570ad38b0cc5ff2e5e019ecd9bde249ba405023",
   "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "refusals": "45fb724cc5c4f4b809d81561866376313a6deee1633f27933aef93a6c4e09b03",
   "run_record": "6e20e49fb1270d57699f033574f6354c86cb24a15794d90c3ee46828f89184eb",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "refused",
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
  },
  "missing|final": {
   "exit": 6,
   "n_orders": 5,
   "nav_gate_csv": "3e17b6fc3741ec740818874935a3a078f2b300f7ee49a86dd1204828f1597100",
   "orders": "9b7f367c05673eb6e51a7617ca8c1e3df33a1ac8b670a8d0b2b3e41904843b07",
   "plan_json": "ce0d283983fb816adf875d84252a324c0c886d7e8db65dc1fd6440f52a043d4d",
   "plan_sha": "424ed40c4df4bf5ad166484b392ab1062cc948ad894722444930904bdf534a82",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "049163f3202d3e035d0cdf5c95a6cedb809066e50466923212ef24cd57f09f7b",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "decided",
   "targets": "5b9f106426de44eaeb18641a86c3f53452d223ae4fc466df6df9970d7dbc2036"
  },
  "missing|final_cls": {
   "exit": 0,
   "n_orders": 5,
   "nav_gate_csv": "3e17b6fc3741ec740818874935a3a078f2b300f7ee49a86dd1204828f1597100",
   "orders": "71adff005d8e0ea1f5f46af244f5d3b547961dacc8c0a0c2a091ec089f6f1e67",
   "plan_json": "6fceb8179dc3273a80ecf5dcb7c5e9ce4fca08424f414783df4d36f121535629",
   "plan_sha": "f6095fcfa894c6253137a628d3d00190547065d3c51db6634ce0c33c80e2caee",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "d298afff744e3c41f39369b5c44f012d0bcda86e3360c7ffda46729f61785934",
   "sent": "6f7bccd5afbf21a8e7298cff39b9c1e238f3252e6a6da0c56204624bb01dfc85",
   "status": None,
   "targets": "5b9f106426de44eaeb18641a86c3f53452d223ae4fc466df6df9970d7dbc2036"
  }
 }
}


def _not_vacuous(got: dict):
    """Both variants decide and send a complete day; the key absent refuses every
    missing-NAV day; the key set holds the fund at the final check and decides."""
    for v in ("absent", "hold"):
        assert got[v]["complete|decide"]["exit"] == rn.EXIT_PLANNED
        assert got[v]["complete|decide"]["n_orders"] > 0
        assert got[v]["complete|send"]["exit"] == rn.EXIT_SENT
        assert got[v]["missing|eve"]["exit"] == rn.EXIT_REFUSED
    assert {got["absent"][f"missing|{x}"]["exit"] for x in ("final", "final_cls")} == \
        {rn.EXIT_REFUSED}
    assert got["hold"]["missing|final"]["exit"] == rn.EXIT_PLANNED
    assert got["hold"]["missing|final_cls"]["exit"] == rn.EXIT_SENT


def test_synthetic_default_deps_is_862b1d0(tmp_path, monkeypatch):
    got = _synthetic_pins(tmp_path, monkeypatch)
    for v in ("absent", "hold"):
        assert got[v]["book"] == SYN_PINNED[v]["book"], (
            f"today's book json ({v}) is not the one this pin was made on: what the runner "
            f"reads from it changed. Re-derive the pin on the release it ships with (module "
            f"docstring)")
    assert got == SYN_PINNED
    _not_vacuous(got)


@pytest.mark.skipif(not _real_panel_ready(), reason="real CEF panels absent (data/ is "
                                                     "gitignored); the synthetic pin still runs")
def test_real_panel_default_deps_is_862b1d0(tmp_path, monkeypatch):
    from src.deploy.sleeves import cef_discount as cefmod
    real = {f: f.read_bytes() for f in (cefmod.PX_PATH, cefmod.NAV_PATH)}
    got = _real_pins(tmp_path, monkeypatch)
    if got is None:
        import warnings
        why = (f"REAL-PANEL ROW-6A NO-OP PIN NOT APPLIED: it was made on panel/spec "
               f"{COMBINE_PINNED_INPUT} (test_combine_noop's v8 input pin); this tree's copy "
               f"differs. The synthetic pin still runs")
        warnings.warn(why, RealPanelPinNotApplicable)
        pytest.skip(why)
    assert got == REAL_PINNED
    _not_vacuous(got)
    assert all(f.read_bytes() == b for f, b in real.items()), "a real panel changed"


TRADES = ("exit", "n_orders", "orders", "plan_sha", "targets", "refusals", "sent", "status")


def _released_not_vacuous(got: dict, gate_absent: dict):
    """The released book's gate changed nothing that trades: every scenario's
    exit, orders, plan_sha, targets, refusals and what reached the broker equal
    the gate-absent pin's `hold` (the same book without the gate block), while
    plan.json and the run records differ by the gate's own record."""
    r, h = got["released"], gate_absent["hold"]
    for scen, hashes in r.items():
        if scen == "book":
            continue
        for k in TRADES:
            if k in hashes:
                assert hashes[k] == h[scen][k], (scen, k)
    assert r["complete|decide"]["plan_json"] != h["complete|decide"]["plan_json"]


def test_synthetic_released_book_is_862b1d0(tmp_path, monkeypatch):
    got = _released_synthetic_pins(tmp_path, monkeypatch)
    assert got["released"]["book"] == RELEASED_SYN_PINNED["released"]["book"], (
        "today's released book json is not the one this pin was made on: what the runner "
        "reads from it changed. Re-derive the pin on the release it ships with (module "
        "docstring)")
    assert got == RELEASED_SYN_PINNED
    _released_not_vacuous(got, SYN_PINNED)


@pytest.mark.skipif(not _real_panel_ready(), reason="real CEF panels absent (data/ is "
                                                     "gitignored); the synthetic pin still runs")
def test_real_panel_released_book_is_862b1d0(tmp_path, monkeypatch):
    from src.deploy.sleeves import cef_discount as cefmod
    real = {f: f.read_bytes() for f in (cefmod.PX_PATH, cefmod.NAV_PATH)}
    got = _released_real_pins(tmp_path, monkeypatch)
    if got is None:
        import warnings
        why = (f"REAL-PANEL RELEASED-BOOK PIN NOT APPLIED: it was made on panel/spec "
               f"{COMBINE_PINNED_INPUT} (test_combine_noop's v8 input pin); this tree's copy "
               f"differs. The synthetic pin still runs")
        warnings.warn(why, RealPanelPinNotApplicable)
        pytest.skip(why)
    assert got == RELEASED_REAL_PINNED
    _released_not_vacuous(got, REAL_PINNED)
    assert all(f.read_bytes() == b for f, b in real.items()), "a real panel changed"


def test_the_core_books_refresh_is_the_command_it_always_was(monkeypatch):
    """The refresh `default_deps` builds for the released book runs fetch_daily
    with exactly the flags it always has (test_run.py pins refresh_subprocess's
    own list; this pins that default_deps still calls it so)."""
    from quantt.broker import alpaca
    got = {}

    def fake_run(cmd, **kw):
        got["cmd"] = cmd
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(rn.subprocess, "run", fake_run)
    monkeypatch.setattr(alpaca.AlpacaClient, "from_environment",
                        classmethod(lambda cls, name, **kw: object()))
    b = rn.BOOKS["cef"]
    deps = rn.default_deps(b, rn.load_spec(b.spec_path), {"QUANTT_ENV_FILE": "unused"})
    r = deps.refresh(dt.date(2026, 9, 28), 600.0)
    assert r.exit == 0 and r.incomplete is None
    assert got["cmd"][1].endswith("scripts/cef/fetch_daily.py")
    assert got["cmd"][2:] == ["--require-asof", "2026-09-28", "--nav-fallback", "cefconnect",
                              "--book", "ops/books/cef_discount_book.json"]
