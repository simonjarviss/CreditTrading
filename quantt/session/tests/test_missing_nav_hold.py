"""Gate 5's missing-NAV hold (book json `data.missing_nav`): DARK, and what it does when on.

THE CASE (2026-10-22, prod's records, read 2026-10-29). PDO's NAV for the as-of
2026-10-21 never reached the panel: fetch_daily exited 4 on every slot, its
CEFConnect fallback failing with JSONDecodeError (CEFConnect has refused every
scripted request from the VM since 2026-10-21), and gate 5 refused all 13
names: "[data] refresh for as-of 2026-10-21 exited 4; [data] NAV not dated
2026-10-21 for {'PDO': '2026-10-20'}". The book missed the day. The team lead
(2026-10-29): with `data.missing_nav = "hold"`, such a fund keeps its shares and
leaves the cross-section from the final check, and the other funds trade
(`quantt/session/gate.py` `missing_nav_hold`).

WHAT IS PROVED HERE

  1. THE NO-OP. With the key ABSENT the session is byte-identical to bd87144
     (release-20261029-1, what prod runs): exit, plan.json, plan_sha, orders,
     targets, the run record, nav_gate.csv, send.json and what reached the
     broker, on a complete day (decide, then send) and on a day with one as-of
     NAV missing (the evening decide, the final check in late-market mode and in
     `cls` mode). The session is built as `default_deps` builds it for the
     released book json: late_market with bp_shortfall "scale", the stale-NAV
     gate in `report` (its CEFConnect reader refusing every request, as prod's
     has since 10-21) and the drawdown check in `report`.
       * `test_synthetic_key_absent_is_bd87144` NEVER SKIPS: the generated
         13-fund panel of test_combine_noop.py and its fixture spec.
       * `test_real_panel_key_absent_is_bd87144`: the real sleeve, a copy of the
         real panels through 2026-09-25 (test_combine_noop's input pin), and the
         core's spec AS IT WAS BEFORE CEF TRIAL 53 (v7), read from git at 35b429f
         (test_combine_noop's `pre_trial_spec`). Until 2026-11-01 this read the
         live spec, which then was v7. bd87144's code cannot run v8's
         `sizing_multiplier`, so the code-versus-code proof keeps v7, and
         survives the activation. It warns and skips when the copy or that spec
         is not what the pin was made on, or when git cannot show it.
     HOW THE PINS WERE MADE: `git archive bd87144` into a scratch directory
     (the real data/ symlinked in, read only), this file copied into that tree,
     and `print_pins()` run there unseeded and under PYTHONHASHSEED 1; then on
     this tree (identical every time). Every tmp path is replaced by `<WORK>`
     before hashing (the drawdown record names its state file). To re-derive,
     do exactly that again; never edit a hash by hand.
  2. THE KEY ON, each test failing on bd87144 (which has no key: the attribute
     set on its Deps is read by nothing, and gate 5 refuses the day):
       * the 2026-10-22 replay: at the final check the other 12 decide and the
         fund without its NAV is held -- on the synthetic panel (never skips),
         and on the real panel through 2026-10-21 with prod's 14:30 ET account
         (skips unless a panel reaching 2026-10-21 is present; point
         QUANTT_REPLAY_PANEL_DIR at a copy of prod's data/cef to run it);
       * more missing NAVs than `gate.max_missing_nav_holds` still refuses;
       * a missing price still refuses, with gate 5's refusals unchanged;
       * a held name is never zeroed, and never the cause of the `min_names`
         flatten.

Hermetic: test_run's FakeClient for the broker, fixed clocks, the refresh a
fixture, no CEFConnect (a reader that raises), netguard refuses any socket.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

import pandas as pd
import pytest

from quantt.session import nav_gate as ng
from quantt.session import run as rn
from quantt.session.tests.test_combine_noop import (
    LIVE_SPEC_PATH,
    PINNED_INPUT as COMBINE_PINNED_INPUT,
    pre_trial_spec,
    SYN_SPEC,
    SYN_TICKERS,
    RealPanelPinNotApplicable,
    _client,
    _frozen_copy,
    _real_panel_ready,
    _sent,
    _write_synthetic,
)
from quantt.session.tests.test_run import BOOK, LATE
from src.deploy.sleeve import FLAT

ET = rn.gt.ET
ASOF = dt.date(2026, 9, 25)                                  # Friday; the session is Monday
SESSION = dt.date(2026, 9, 28)
EVE = dt.datetime(2026, 9, 25, 22, 0, tzinfo=ET)             # the evening decide: never final
MORNING = dt.datetime(2026, 9, 28, 10, 0, tzinfo=ET)         # a morning slot, before the final
FINAL = dt.datetime(2026, 9, 28, 14, 30, 1, tzinfo=ET)       # the 14:30 slot: close - 90 min
SEND = dt.datetime(2026, 9, 28, 15, 52, 30, tzinfo=ET)       # inside 15:52-15:58
LATE_SCALE = {**LATE, "bp_shortfall": "scale"}               # the released execution block
CLS_SCALE = {"mode": "cls", "bp_shortfall": "scale"}
HOLD = "hold"
SYN_MISSING = "SYD"            # the synthetic fund whose as-of NAV is removed
REAL_MISSING = "PDO"           # the real one (2026-10-22's)


def _sha(b) -> str:
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


class _Quiet:
    def __init__(self):
        self.text = []

    def write(self, s):
        self.text.append(s)

    def flush(self):
        return None


def _refused(ticker, days):
    """CEFConnect as prod has read it since 2026-10-21: every request refused."""
    raise ng.CefConnectError(f"{ticker}: JSONDecodeError: Expecting value: line 1 column 1 "
                             f"(char 0)")


# ------------------------------------------------------------------ panels

def _scenario_panel(base: Path, dst: Path, mp, asof, *, nav=(), close=()):
    """A copy of the panels in `base` at `dst`, the sleeve pointed at it, with the
    rows DATED `asof` of the names in `nav` (NAV) and `close` (price) removed."""
    from src.deploy.sleeves import cef_discount as cefmod
    dst.mkdir(parents=True)
    for name, drop in (("cef_prices.parquet", close), ("cef_nav.parquet", nav)):
        df = pd.read_parquet(base / name)
        if drop:
            m = (pd.to_datetime(df["date"]) == pd.Timestamp(asof)) & df["ticker"].isin(list(drop))
            assert int(m.sum()) == len(drop), (name, drop, int(m.sum()))
            df = df[~m].reset_index(drop=True)
        df.to_parquet(dst / name)
    mp.setattr(cefmod, "PX_PATH", dst / "cef_prices.parquet")
    mp.setattr(cefmod, "NAV_PATH", dst / "cef_nav.parquet")
    mp.setattr(cefmod, "GRP_PATH", dst / "cef_prices.parquet")


def _synthetic_base(work: Path, mp) -> Path:
    base = work / "base"
    base.mkdir(parents=True)
    _write_synthetic(base)
    return base


def _synthetic_held(work: Path, mp):
    """(base panel dir, held book): the synthetic panel, and test_combine_noop's held
    book computed on a complete copy of it."""
    base = _synthetic_base(work, mp)
    _scenario_panel(base, work / "complete_panel", mp, ASOF)
    held = _held_book(SYN_SPEC, ASOF, SYN_SPEC["capital_usd"])
    assert held and any(q > 0 for q in held.values()) and any(q < 0 for q in held.values())
    return base, held


def _held_book(spec, asof, cap):
    """Half the day-one book (test_combine_noop's held book): trades and band holds."""
    from src.deploy.sleeves import cef_discount as cefmod
    uni = rn.spec_params(spec)["universe"]
    closes = {s: v[0] for s, v in rn.last_closes(cefmod.PX_PATH, asof, uni).items()}
    day1 = rn.sleeve_targets(spec, cap, asof, {}, cap, True)
    held = {t.instrument: int(0.5 * cap * float(t.weight) / closes[t.instrument])
            for t in day1 if t.weight}
    return {s: q for s, q in held.items() if q}


# ------------------------------------------------------------------ one session

# The hold's age limit as the team lead set it (2026-10-29): the tests' book json value.
MAX_SESSIONS = 2


def _prior_plan(session: dt.date, missing=None, *, key_on=True, refusals=()) -> dict:
    """A prior session's plan.json, reduced to what `run.missing_nav_streaks` reads:
    with the key on, its `missing_nav.missing`; with it off, its refusals."""
    plan = {"session_date": session.isoformat(), "refusals": list(refusals)}
    if key_on:
        plan["missing_nav"] = {"mode": HOLD, "missing": dict(missing or {}), "held": []}
    return plan


def _write_priors(state: Path, prior: dict):
    for d, plan in prior.items():
        (state / d.isoformat()).mkdir(parents=True, exist_ok=True)
        f = state / d.isoformat() / "plan.json"
        f.write_text(plan if isinstance(plan, str) else json.dumps(plan))


def _session(work: Path, spec, held, now, execution, *, refresh_exit, key=None, armed=False,
             account=None, asof=ASOF, session=SESSION, prior=None, max_sessions=MAX_SESSIONS):
    """One run_session, built as default_deps builds it for the released book json
    (stale-NAV gate and drawdown check in report mode), on the sleeve's (patched)
    panels. `key`, when given, is set as `deps.missing_nav` (and `max_sessions` as
    `deps.missing_nav_max_sessions`) AFTER the Deps is built, so the same code runs
    on bd87144, whose Deps has neither field and never reads them. With the key on,
    `prior` ({session date: plan dict, or raw text}) is written to the state dir
    first; None writes the previous session's plan with every NAV dated (the
    age limit's count starts at 0). Returns (exit, state dir, client, log text)."""
    from ops.schedule.nyse_calendar import previous_trading_day
    from src.deploy.sleeves import cef_discount as cefmod
    p = rn.spec_params(spec)
    cap = p["capital_usd"]
    state = work / "state"
    state.mkdir(parents=True, exist_ok=True)
    if key is not None:
        prev = previous_trading_day(session)
        _write_priors(state, {prev: _prior_plan(prev)} if prior is None else prior)
    if armed:
        (state / "AUTO_ARMED").touch()
    closes = {s: v[0] for s, v in rn.last_closes(cefmod.PX_PATH, asof, p["universe"]).items()}
    c = _client(state, held, closes, now)
    for k, v in (account or {}).items():
        setattr(c, k, v)
    out = _Quiet()
    deps = rn.Deps(
        client=c, env={"QUANTT_STATE_DIR": str(state), "DRY_RUN": "0"},
        refresh=lambda a, t: rn.RefreshResult(exit=refresh_exit, tail="fixture"),
        closes=lambda a, u: rn.last_closes(cefmod.PX_PATH, a, u),
        navs=lambda a, u: rn.last_navs(cefmod.NAV_PATH, a, u),
        history=lambda a, u, r: rn.close_history(cefmod.PX_PATH, a, u, r),
        targets=lambda a, h, eq, op, **kw: rn.sleeve_targets(spec, cap, a, h, eq, op, **kw),
        halts=lambda: [], utcnow=lambda: now.astimezone(dt.timezone.utc), out=out,
        execution=execution, stale_nav=ng.REPORT,
        nav_gate=ng.PanelGate(nav_path=cefmod.NAV_PATH, reader=_refused),
        drawdown="report")
    if key is not None:
        deps.missing_nav = key
        deps.missing_nav_max_sessions = max_sessions
    code = rn.run_session(BOOK, spec, deps)
    return code, state, c, "".join(out.text)


def _plan(state, day=SESSION) -> dict:
    return json.loads((state / day.isoformat() / "plan.json").read_text())


def _norm(raw: bytes, work: Path) -> bytes:
    return raw.replace(str(work).encode(), b"<WORK>")


def _hashes(work: Path, state: Path, code: int, client, *, send=False) -> dict:
    day = state / SESSION.isoformat()
    runs = sorted((day / "runs").glob("*.json"))
    out = {"exit": code, "run_record": _sha(_norm(runs[-1].read_bytes(), work)),
           "sent": _sha(json.dumps(_sent(client)))}
    if send:
        out["send_json"] = _sha(_norm((day / "send.json").read_bytes(), work))
        return out
    raw = (day / "plan.json").read_bytes()
    plan = json.loads(raw)
    out.update(plan_json=_sha(_norm(raw, work)), plan_sha=plan["plan_sha"],
               status=plan.get("status"), n_orders=len(plan["orders"]),
               orders=_sha(json.dumps(plan["orders"], sort_keys=True)),
               targets=_sha(json.dumps(plan["targets"], sort_keys=True)),
               refusals=_sha(json.dumps(plan["refusals"], sort_keys=True)),
               nav_gate_csv=(_sha(_norm((state / ng.CSV_NAME).read_bytes(), work))
                             if (state / ng.CSV_NAME).exists() else None))
    return out


def _absent_scenarios(work: Path, base: Path, mp, spec, missing: str) -> dict:
    """Every pinned output with the key ABSENT (module docstring, 1)."""
    out = {}
    _scenario_panel(base, work / "complete" / "panel", mp, ASOF)
    cap = rn.spec_params(spec)["capital_usd"]
    held = _held_book(spec, ASOF, cap)
    w = work / "complete"
    code, state, c, _ = _session(w, spec, held, EVE, LATE_SCALE, refresh_exit=0)
    out["complete|decide"] = _hashes(w, state, code, c)
    code, state, c, _ = _session(w, spec, held, SEND, LATE_SCALE, refresh_exit=0, armed=True)
    out["complete|send"] = _hashes(w, state, code, c, send=True)
    for label, now, ex, armed in (("eve", EVE, LATE_SCALE, False),
                                  ("final", FINAL, LATE_SCALE, False),
                                  ("final_cls", FINAL, CLS_SCALE, True)):
        w = work / f"missing_{label}"
        _scenario_panel(base, w / "panel", mp, ASOF, nav=(missing,))
        code, state, c, _ = _session(w, spec, held, now, ex, refresh_exit=4, armed=armed)
        out[f"missing|{label}"] = _hashes(w, state, code, c)
    return out


def _synthetic_pins(work: Path, mp) -> dict:
    return _absent_scenarios(work, _synthetic_base(work, mp), mp, SYN_SPEC, SYN_MISSING)


def _real_pins(work: Path, mp) -> dict | None:
    """None when git cannot show the pre-trial spec, or the real copy or that spec is not
    what the pin was made on."""
    pre = pre_trial_spec()
    if pre is None:
        return None
    raw, spec = pre
    base = work / "base"
    base.mkdir(parents=True)
    got = {"panel": _frozen_copy(base, mp, spec["frozen"]["universe"]),
           "spec": _sha(raw)}
    if got != COMBINE_PINNED_INPUT:
        return None
    return _absent_scenarios(work, base, mp, spec, REAL_MISSING)


def print_pins():
    """Print both pins (module docstring, HOW THE PINS WERE MADE)."""
    import tempfile
    with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
        print("SYN_PINNED =", json.dumps(_synthetic_pins(Path(d) / "syn", mp), indent=1,
                                          sort_keys=True))
    with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
        print("REAL_PINNED =", json.dumps(_real_pins(Path(d) / "real", mp), indent=1,
                                           sort_keys=True))


# PINNED 2026-10-29 on bd87144 (module docstring: how, and how to re-derive).
SYN_PINNED = {
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
        "targets": "732894a285fe4821a443ae4ce9d9d609cc3e382edc831ccb239c03e155f5fb6f",
    },
    "complete|send": {
        "exit": 0,
        "run_record": "2ba2408c6f4f2039f65594d86948e8d88ef22afaf654b6d118f60f35dc3babee",
        "send_json": "28900ab87d89f8716cc885b35b3612f9f9b33ca0be117b85d12659cbd5624819",
        "sent": "5409c95d63e197ab80437a44fa71fb69e234f2578348b84b75cc9217193f6aaf",
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
        "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
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
        "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
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
        "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
    },
}
REAL_PINNED = {
    "complete|decide": {
        "exit": 6,
        "n_orders": 6,
        "nav_gate_csv": "18734cfdbe33cc779a2277bef135248fcafa1c90de9b2a0c203ae82a729af304",
        "orders": "f198dd92f1f473578190d104e61bd70d8bb2352ecb253bc12ccc6c9b23d75a2c",
        "plan_json": "46a4beb72f9164c126769a765a2c350144262d9cc2c77240f3e7be5fa39a7d30",
        "plan_sha": "e69a46f6680840664ed3b44e21eb767cf4d9f641e0b3f9ee0fd07e45fa084e05",
        "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "run_record": "ef7329ad8ebfaccef04d1e0eb58d8b9a719bb1369f3be2407e2a23c5a3ecc6c3",
        "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "status": "decided",
        "targets": "978e2df32387f0be9e49a3a5966369bed1866e780b1ca8d79d562d11f2c37f56",
    },
    "complete|send": {
        "exit": 0,
        "run_record": "8003b25c902c0bc09863598ac0910fe44e0ca3ce245b912b05e8f07c28d37003",
        "send_json": "ac1adb88597ac75eb557fc634eae9f879b5196a07c03cdbbcfc05fa2a46d6a9b",
        "sent": "b30cc665d139dfebf931d9cac73299e66c22518a92a49e5c70d6a68e9532139d",
    },
    "missing|eve": {
        "exit": 11,
        "n_orders": 0,
        "nav_gate_csv": None,
        "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "plan_json": "52e45d9baa3c8d5cd7a2e9e0cee5341c5f7f0d3347e7b2b6dc86b24953f752f3",
        "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "refusals": "0bd11e7d2acb6a4d1333ffa81814bd978c4247336c94639a7005ddcefcb9a865",
        "run_record": "35f91aaac82e1f8865858e33dfce21928282a0da31889e7e3a3cd692e3258931",
        "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "status": "refused",
        "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
    },
    "missing|final": {
        "exit": 11,
        "n_orders": 0,
        "nav_gate_csv": None,
        "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "plan_json": "52e45d9baa3c8d5cd7a2e9e0cee5341c5f7f0d3347e7b2b6dc86b24953f752f3",
        "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "refusals": "0bd11e7d2acb6a4d1333ffa81814bd978c4247336c94639a7005ddcefcb9a865",
        "run_record": "ace60f3823f434048528b0a37871dabde32a64435cb42cff43fb096a0ad70fc7",
        "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "status": "refused",
        "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
    },
    "missing|final_cls": {
        "exit": 11,
        "n_orders": 0,
        "nav_gate_csv": None,
        "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "plan_json": "f783d446fc82ca1ca6f78e2a8caa3b7973224132afbe2905e7b7dd32d34fda0c",
        "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "refusals": "0bd11e7d2acb6a4d1333ffa81814bd978c4247336c94639a7005ddcefcb9a865",
        "run_record": "494b3176742219873c4938795cf82efa8dce534907245657dbdfe9bb436d015a",
        "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
        "status": None,
        "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
    },
}


# ------------------------------------------------------------- 1. the no-op

def test_the_released_book_json_sets_the_hold_as_ruled(monkeypatch):
    """The team lead switched the hold on, 2026-10-29: `hold`, at most 2 sessions.

    Until that ruling this test pinned the key ABSENT (the dark release,
    release-20261029-2). It now pins the ruled values, so a later edit that drops
    the key or changes the limit fails here and has to say so."""
    b = rn.BOOKS["cef"]
    data = json.loads(b.book_path.read_text()).get("data") or {}
    assert data.get("missing_nav") == "hold"
    assert data.get("missing_nav_max_sessions") == 2
    assert "_missing_nav_note" in data
    assert rn.missing_nav_for(b) == "hold"
    assert rn.missing_nav_max_sessions_for(b) == 2
    from quantt.broker import alpaca
    monkeypatch.setattr(alpaca.AlpacaClient, "from_environment",
                        classmethod(lambda cls, book, **kw: object()))
    assert rn.default_deps(b, rn.load_spec(b.spec_path),
                           {"QUANTT_ENV_FILE": "unused"}).missing_nav is not None


def test_synthetic_key_absent_is_bd87144(tmp_path, monkeypatch):
    got = _synthetic_pins(tmp_path, monkeypatch)
    assert got == SYN_PINNED
    # Not vacuous: a complete day decides and sends; a missing NAV refuses it.
    assert got["complete|decide"]["exit"] == rn.EXIT_PLANNED
    assert got["complete|decide"]["n_orders"] > 0
    assert got["complete|send"]["exit"] == rn.EXIT_SENT
    assert {got[f"missing|{x}"]["exit"] for x in ("eve", "final", "final_cls")} == \
        {rn.EXIT_REFUSED}


@pytest.mark.skipif(not _real_panel_ready(), reason="real CEF panels absent (data/ is "
                                                     "gitignored); the synthetic pin still runs")
def test_real_panel_key_absent_is_bd87144(tmp_path, monkeypatch):
    from src.deploy.sleeves import cef_discount as cefmod
    real = {f: f.read_bytes() for f in (cefmod.PX_PATH, cefmod.NAV_PATH)}
    got = _real_pins(tmp_path, monkeypatch)
    if got is None:
        why = (f"REAL-PANEL MISSING-NAV NO-OP PIN NOT APPLIED: it was made on panel/spec "
               f"{COMBINE_PINNED_INPUT} (test_combine_noop's input pin; the spec is the "
               f"pre-trial v7, read from git); this tree's copy differs, or git cannot show "
               f"that spec. The synthetic pin still runs")
        import warnings
        warnings.warn(why, RealPanelPinNotApplicable)
        pytest.skip(why)
    assert got == REAL_PINNED
    assert got["complete|decide"]["exit"] == rn.EXIT_PLANNED
    assert all(f.read_bytes() == b for f, b in real.items()), "a real panel changed"


# ---------------------------------------------- 2. the key on: the 10-22 replay

def _decided_with_hold(state, held, missing: str, n_universe: int, day=SESSION):
    """The plan decided, `missing` held at its current shares with no order, and
    every other fund decided by the signal (not held, not flattened)."""
    plan = _plan(state, day)
    assert plan["refusals"] == [], plan["refusals"]
    assert plan.get("status", "decided") == "decided"
    t = plan["targets"][missing]
    assert t["current"] == held.get(missing, 0) and t["target"] == held.get(missing, 0), t
    assert "NAV unverified: no NAV dated" in t["reason"], t["reason"]
    assert missing not in {o["symbol"] for o in plan["orders"]}
    others = {s: x for s, x in plan["targets"].items() if s != missing}
    assert len(others) == n_universe - 1
    for s, x in others.items():
        assert "NAV unverified" not in x["reason"] and "book holds" not in x["reason"], (s, x)
        assert "eligible names" not in x["reason"], (s, x)
    rec = plan["missing_nav"]
    assert rec["action"] == "held" and rec["held"] == [missing] and rec["final_check"] is True
    assert set(rec["missing"]) == {missing}
    return plan


def test_replay_2026_10_22_on_the_synthetic_panel(tmp_path, monkeypatch):
    """The 10-22 shape on the panel that never skips: one fund, FLAT (PDO held no
    shares that day), lacks its as-of NAV; the refresh says INCOMPLETE (exit 4).
    Evening: deferred (refused, today's refusals plus the deferral line). The
    final check: the other 12 decide, the fund is held -- and the plan is sent."""
    base, held = _synthetic_held(tmp_path, monkeypatch)
    _scenario_panel(base, tmp_path / "p", monkeypatch, ASOF, nav=(SYN_MISSING,))
    held.pop(SYN_MISSING, None)                          # flat, as PDO was
    # The evening decide: deferred, never decided.
    code, state, _, log = _session(tmp_path / "eve", SYN_SPEC, held, EVE, LATE_SCALE,
                                   refresh_exit=4, key=HOLD)
    absent, astate, _, _ = _session(tmp_path / "eve_absent", SYN_SPEC, held, EVE, LATE_SCALE,
                                    refresh_exit=4)
    assert code == absent == rn.EXIT_REFUSED
    eve, base_plan = _plan(state), _plan(astate)
    assert eve["refusals"][:-1] == base_plan["refusals"]          # today's, unchanged
    assert "deferred" in eve["refusals"][-1]["detail"] and eve["refusals"][-1]["gate"] == "data"
    assert eve["missing_nav"]["action"] == "deferred" and eve["missing_nav"]["held"] == []
    assert not (state / SESSION.isoformat() / "DECIDED").exists()
    # A morning slot before the final check: still deferred.
    code, state, _, _ = _session(tmp_path / "morning", SYN_SPEC, held, MORNING, LATE_SCALE,
                                 refresh_exit=4, key=HOLD)
    assert code == rn.EXIT_REFUSED and _plan(state)["missing_nav"]["action"] == "deferred"
    # The final check: decided; PDO's twin held; the run record says so too.
    code, state, _, log = _session(tmp_path / "final", SYN_SPEC, held, FINAL, LATE_SCALE,
                                   refresh_exit=4, key=HOLD)
    assert code == rn.EXIT_PLANNED, log
    plan = _decided_with_hold(state, held, SYN_MISSING, len(SYN_TICKERS))
    assert plan["orders"], "nothing traded: the replay would be vacuous"
    run = json.loads(sorted((state / SESSION.isoformat() / "runs").glob("*.json"))[-1]
                     .read_text())
    assert run["missing_nav"]["held"] == [SYN_MISSING]
    assert "MISSING NAV (hold)" in log and "HELD" in log
    # The stale-NAV gate ran on the exit-4 refresh (it does not under bd87144).
    assert "not_run" not in plan["nav_gate"] and plan["nav_gate"]["refresh_exit"].startswith("4")
    # And the decided plan is what the send sends.
    code, state, c, _ = _session(tmp_path / "final", SYN_SPEC, held, SEND, LATE_SCALE,
                                 refresh_exit=4, key=HOLD, armed=True)
    assert code == rn.EXIT_SENT
    assert [o[1] for o in _sent(c)] and SYN_MISSING not in {o[1] for o in _sent(c)}


def test_replay_2026_10_22_in_cls_mode_decides_and_sends_at_the_final_check(tmp_path,
                                                                            monkeypatch):
    base, held = _synthetic_held(tmp_path, monkeypatch)
    _scenario_panel(base, tmp_path / "p", monkeypatch, ASOF, nav=(SYN_MISSING,))
    code, state, c, log = _session(tmp_path / "cls", SYN_SPEC, held, FINAL, CLS_SCALE,
                                   refresh_exit=4, key=HOLD, armed=True)
    assert code == rn.EXIT_SENT, log
    _decided_with_hold(state, held, SYN_MISSING, len(SYN_TICKERS))
    assert _sent(c) and SYN_MISSING not in {o[1] for o in _sent(c)}


# Prod's 2026-10-22 14:30 ET decide (runs/20261022T183001Z-run.json on the VM,
# copied read-only 2026-10-29): the broker's positions and account at that slot.
# Broker figures from prod's own record, for the replay only; nothing sizes on them.
REPLAY_ASOF = dt.date(2026, 10, 21)
REPLAY_SESSION = dt.date(2026, 10, 22)
REPLAY_FINAL = dt.datetime(2026, 10, 22, 14, 30, 1, tzinfo=ET)
REPLAY_POSITIONS = {"AWF": -237, "BIT": 1284, "DSL": 1354, "HYT": -274, "JFR": -2711,
                    "MQY": -2522, "PCN": 502, "PDI": -60, "PFN": 2204, "PHK": 4577, "PTY": -129}
REPLAY_ACCOUNT = {"equity": 99062.6, "bp": 184622.75, "regt_bp": 72583.86,
                  "long_mv": 65115.13, "short_mv": -52311.34, "maint": 52906.91}


def _replay_source() -> Path:
    from src.deploy.sleeves import cef_discount as cefmod
    env = os.environ.get("QUANTT_REPLAY_PANEL_DIR")
    return Path(env) if env else cefmod.PX_PATH.parent


def _replay_panel_ready(src: Path, universe) -> bool:
    """The panel holds a close and a NAV dated REPLAY_ASOF for every deployed name."""
    try:
        P = pd.read_parquet(src / "cef_prices.parquet", columns=["date", "ticker", "close"])
        N = pd.read_parquet(src / "cef_nav.parquet", columns=["date", "ticker", "nav"])
    except (FileNotFoundError, OSError):
        return False
    ts = pd.Timestamp(REPLAY_ASOF)
    return all(set(universe) <= set(df.loc[pd.to_datetime(df["date"]) == ts, "ticker"])
               for df in (P, N))


def replay_2026_10_22(work: Path, mp, src: Path):
    """The real sleeve and live spec on the panel in `src` cut at 2026-10-21, PDO's
    10-21 NAV removed (prod's panel at 14:30 ET on 10-22 ended 10-20 for PDO),
    prod's positions and account, the final-check slot, the key on."""
    spec = json.loads(LIVE_SPEC_PATH.read_text())
    uni = spec["frozen"]["universe"]
    base = work / "base"
    base.mkdir(parents=True)
    for name in ("cef_prices.parquet", "cef_nav.parquet"):
        df = pd.read_parquet(src / name)
        df = df[df["ticker"].isin(uni) & (pd.to_datetime(df["date"]) <= pd.Timestamp(REPLAY_ASOF))]
        df.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True).to_parquet(
            base / name)
    _scenario_panel(base, work / "p", mp, REPLAY_ASOF, nav=(REAL_MISSING,))
    from src.deploy.sleeves import cef_discount as cefmod
    assert rn.last_navs(cefmod.NAV_PATH, REPLAY_ASOF, uni)[REAL_MISSING] == dt.date(2026, 10, 20)
    # Prod's 10-21 plan.json was decided with the key off and no refusal (gate 5
    # passed: every NAV dated), so the age limit's count starts at 0.
    prev = dt.date(2026, 10, 21)
    code, state, c, log = _session(work / "s", spec, REPLAY_POSITIONS, REPLAY_FINAL,
                                   LATE_SCALE, refresh_exit=4, key=HOLD,
                                   account=REPLAY_ACCOUNT, asof=REPLAY_ASOF,
                                   session=REPLAY_SESSION,
                                   prior={prev: _prior_plan(prev, key_on=False)})
    return code, state, log


def test_replay_2026_10_22_on_the_real_panel(tmp_path, monkeypatch):
    spec = json.loads(LIVE_SPEC_PATH.read_text())
    src = _replay_source()
    if not _replay_panel_ready(src, spec["frozen"]["universe"]):
        import warnings
        why = (f"2026-10-22 REAL-PANEL REPLAY NOT RUN: {src} has no close and NAV dated "
               f"{REPLAY_ASOF} for every deployed name (set QUANTT_REPLAY_PANEL_DIR to a copy "
               f"of prod's data/cef). The synthetic replay still runs")
        warnings.warn(why, RealPanelPinNotApplicable)
        pytest.skip(why)
    code, state, log = replay_2026_10_22(tmp_path, monkeypatch, src)
    assert code in (rn.EXIT_PLANNED, rn.EXIT_NOTHING), log
    plan = _decided_with_hold(state, REPLAY_POSITIONS, REAL_MISSING,
                              len(spec["frozen"]["universe"]), REPLAY_SESSION)
    assert plan["targets"][REAL_MISSING]["reason"].startswith("cef: not opened, NAV unverified")


# ------------------------------------------- 2. the key on: the guards

def _final(work, mp, base, held, *, nav=(), close=(), key=HOLD, spec=SYN_SPEC, ex=LATE_SCALE):
    _scenario_panel(base, work / "p", mp, ASOF, nav=nav, close=close)
    return _session(work, spec, held, FINAL, ex, refresh_exit=4, key=key)


def test_more_missing_navs_than_the_derived_limit_still_refuses(tmp_path, monkeypatch):
    """The limit is n - min_names, read from the spec (gate.max_missing_nav_holds):
    13 - 6 = 7. Seven missing are held (the control: bd87144 refuses it); eight
    are a broken feed, refused, the reason saying so."""
    base, held = _synthetic_held(tmp_path, monkeypatch)
    n, m = len(SYN_TICKERS), SYN_SPEC["frozen"]["min_names"]
    limit = n - m
    assert limit == 7
    # Seven held, SYM (illiquid on the date) among them: the 6 left are all
    # eligible, so the plan is decided, not refused. (Seven held WITHOUT SYM leave
    # 5 eligible: test_holds_plus_the_sleeves_exclusions_under_min_names_refuse.)
    seven = ("SYM",) + SYN_TICKERS[:limit - 1]
    code, state, _, log = _final(tmp_path / "seven", monkeypatch, base, held, nav=seven)
    assert code in (rn.EXIT_PLANNED, rn.EXIT_NOTHING), log
    plan = _plan(state)
    assert plan["refusals"] == [] and plan["missing_nav"]["held"] == sorted(seven)
    eight = SYN_TICKERS[:limit + 1]
    code, state, _, log = _final(tmp_path / "eight", monkeypatch, base, held, nav=eight)
    assert code == rn.EXIT_REFUSED
    plan = _plan(state)
    assert plan["missing_nav"]["action"] == "refused" and plan["missing_nav"]["held"] == []
    assert any(r["gate"] == "data" and "at most 7 may be held" in r["detail"]
               and "broken feed" in r["detail"] for r in plan["refusals"]), plan["refusals"]
    assert plan["orders"] == [] and plan["status"] == "refused"
    assert plan["missing_nav"]["max_held"] == rn.gt.max_missing_nav_holds(n, m) == limit


def test_a_missing_price_still_refuses(tmp_path, monkeypatch):
    """A fund missing its price, not just its NAV, keeps today's refusal, text for
    text; so does another fund's missing price beside a missing NAV. The control:
    the NAV alone is held (bd87144 refuses it)."""
    base, held = _synthetic_held(tmp_path, monkeypatch)
    code, state, _, _ = _final(tmp_path / "nav_only", monkeypatch, base, held,
                               nav=(SYN_MISSING,))
    assert code == rn.EXIT_PLANNED and _plan(state)["missing_nav"]["held"] == [SYN_MISSING]
    for label, nav, close in (("both", (SYN_MISSING,), (SYN_MISSING,)),
                              ("other", (SYN_MISSING,), ("SYB",))):
        on, on_state, _, _ = _final(tmp_path / f"{label}_on", monkeypatch, base, held,
                                    nav=nav, close=close)
        off, off_state, _, _ = _final(tmp_path / f"{label}_off", monkeypatch, base, held,
                                      nav=nav, close=close, key=None)
        assert on == off == rn.EXIT_REFUSED
        p_on, p_off = _plan(on_state), _plan(off_state)
        assert p_on["refusals"] == p_off["refusals"], "gate 5's refusal must be today's"
        assert any("close not dated" in r["detail"] for r in p_on["refusals"])
        assert p_on["missing_nav"]["action"] == "refused" and "close" in \
            p_on["missing_nav"]["why"]
        assert p_on["orders"] == []


def test_a_held_name_is_never_zeroed_or_flattened(tmp_path, monkeypatch):
    """A held fund long or short keeps exactly its shares; and when the holds leave
    fewer than min_names eligible, the WHOLE BOOK holds (no order, nothing
    flattened): the hold is never the cause of the sleeve's min_names flatten.
    On bd87144 every one of these days is refused."""
    base, held = _synthetic_held(tmp_path, monkeypatch)
    longs = [s for s, q in held.items() if q > 0]
    shorts = [s for s, q in held.items() if q < 0]
    assert longs and shorts
    pair = (longs[0], shorts[0])
    code, state, _, log = _final(tmp_path / "pair", monkeypatch, base, held, nav=pair)
    assert code == rn.EXIT_PLANNED, log
    plan = _plan(state)
    for s in pair:
        t = plan["targets"][s]
        assert t["current"] == t["target"] == held[s] != 0, t
        assert t["reason"].startswith("cef: held, NAV unverified"), t
    assert not set(pair) & {o["symbol"] for o in plan["orders"]}
    # Seven held and SYM illiquid: 5 eligible < min_names 6. Nothing is flattened
    # and no order goes: the day is refused (release-check of 6d42f4f), where
    # 3f817bf decided a whole-book hold and marked the day DONE.
    seven = tuple(s for s in SYN_TICKERS if s != "SYM")[:7]
    assert "SYM" not in seven
    code, state, _, log = _final(tmp_path / "seven", monkeypatch, base, held, nav=seven)
    assert code == rn.EXIT_REFUSED, log
    plan = _plan(state)
    assert plan["orders"] == [] and plan["targets"] == {}
    assert not (state / SESSION.isoformat() / "DONE").exists()


SPEC_MIN12 = json.loads(json.dumps(SYN_SPEC))
SPEC_MIN12["frozen"]["min_names"] = 12      # 13 names: one may be held (13 - 12)


def test_holds_plus_the_sleeves_exclusions_under_min_names_refuse_the_day(tmp_path,
                                                                        monkeypatch):
    """The release-check's case (execution-trader, 6d42f4f). The hold's own cap
    (n - min_names) counts only names without a NAV. With min_names 12, one fund
    may be held; SYM is illiquid on the date, so with SYD held 11 names are
    eligible on their signal, under 12. 3f817bf decided a whole-book hold:
    NOTHING_TO_SEND, DONE, and the 15:00 slot idled. Now the day is refused
    exactly as without the key, the line naming the held fund, the eligible
    count and SYM's exclusion. Control: the same day with every NAV dated
    decides (12 eligible)."""
    base, held = _synthetic_held(tmp_path, monkeypatch)
    assert rn.gt.max_missing_nav_holds(13, 12) == 1
    _scenario_panel(base, tmp_path / "complete", monkeypatch, ASOF)
    code, state, _, log = _session(tmp_path / "control", SPEC_MIN12, held, FINAL, LATE_SCALE,
                                   refresh_exit=0, key=HOLD)
    assert code in (rn.EXIT_PLANNED, rn.EXIT_NOTHING) and _plan(state)["refusals"] == [], log
    assert _plan(state)["missing_nav"]["action"] == "none"
    _scenario_panel(base, tmp_path / "p", monkeypatch, ASOF, nav=(SYN_MISSING,))
    code, state, _, log = _session(tmp_path / "s", SPEC_MIN12, held, FINAL, LATE_SCALE,
                                   refresh_exit=4, key=HOLD)
    off, off_state, _, _ = _session(tmp_path / "off", SPEC_MIN12, held, FINAL, LATE_SCALE,
                                    refresh_exit=4)
    assert code == off == rn.EXIT_REFUSED, log
    plan, today = _plan(state), _plan(off_state)["refusals"]
    assert plan["refusals"][:-1] == today, "gate 5's refusals must be today's"
    last = plan["refusals"][-1]
    assert last["gate"] == "data" and SYN_MISSING in last["detail"]
    assert "11 names are eligible on their signal" in last["detail"]
    assert "under min_names 12" in last["detail"] and "'SYM': 'illiquid'" in last["detail"]
    assert plan["orders"] == [] and plan["targets"] == {} and plan["status"] == "refused"
    rec = plan["missing_nav"]
    assert rec["action"] == "refused" and rec["held"] == []
    assert len(rec["short_of_min_names"]["eligible"]) == 11
    assert not (state / SESSION.isoformat() / "DONE").exists()
    assert not (state / SESSION.isoformat() / "DECIDED").exists()


def test_the_sleeve_counts_a_held_fund_without_a_paired_row_toward_min_names(tmp_path,
                                                                             monkeypatch):
    """At the sleeve: the held funds have no paired row on the date (their NAV is
    missing), so their z is NaN; they are counted toward min_names as possibly
    eligible, and the book holds. bd87144's sleeve skipped them before the count,
    emitted the rest FLAT and kept only the held ones."""
    base, held = _synthetic_held(tmp_path, monkeypatch)
    seven = tuple(s for s in SYN_TICKERS if s != "SYM")[:7]
    _scenario_panel(base, tmp_path / "p", monkeypatch, ASOF, nav=seven)
    from src.deploy.registry import build_sleeve
    from src.deploy.sleeve import MarketState
    sl = build_sleeve(SYN_SPEC, SYN_SPEC["capital_usd"])
    ms = MarketState(asof=pd.Timestamp(ASOF), prices=pd.DataFrame(),
                     holdings={k: float(v) for k, v in held.items()},
                     extras={"sleeve_nav": SYN_SPEC["capital_usd"], "opening_session": False,
                             "nav_hold": {"asof": ASOF, "names": {s: "r" for s in seven}}})
    got = sl.target_positions(pd.Timestamp(ASOF), ms)
    assert {t.instrument for t in got} == set(SYN_TICKERS)
    from src.deploy.sleeves.cef_discount import SHORT_OF_MIN_NAMES
    for t in got:
        q = float(held.get(t.instrument, 0))
        assert (t.qty == q) if q else (t.side == FLAT), t
        assert "book holds" in t.reason, t
        tag = t.meta[SHORT_OF_MIN_NAMES]             # the runner refuses on it
        assert len(tag["eligible"]) == 5 and tag["held_out"] == sorted(seven)
        assert tag["excluded"]["SYM"] == "illiquid"


# ------------------------------------------- the key itself

@pytest.mark.parametrize("data, want", [
    (None, None), ({"stale_nav": "report"}, None), ({"missing_nav": "hold"}, "hold"),
    ({"stale_nav": "report", "missing_nav": "hold", "_missing_nav_note": "x"}, "hold")])
def test_the_key_absent_is_todays_gate_and_hold_is_the_only_mode(tmp_path, data, want):
    path = tmp_path / "book.json"
    path.write_text(json.dumps({"book_id": "b"} if data is None else {"book_id": "b",
                                                                      "data": data}))
    book = rn.Book("cef", "cef", Path("x"), path)
    assert rn.missing_nav_for(book) == want
    assert rn.stale_nav_for(book) == (data or {}).get("stale_nav")


@pytest.mark.parametrize("data", [{"missing_nav": "on"}, {"missing_nav": None},
                                  {"missing_nav": "report"}, {}])
def test_a_missing_nav_setting_that_is_not_hold_raises(tmp_path, data):
    path = tmp_path / "book.json"
    path.write_text(json.dumps({"book_id": "b", "data": data}))
    with pytest.raises(rn.SessionError):
        rn.missing_nav_for(rn.Book("cef", "cef", Path("x"), path))


def test_a_combined_book_with_the_key_fails_naming_it(tmp_path, monkeypatch):
    base = _synthetic_base(tmp_path, monkeypatch)
    _scenario_panel(base, tmp_path / "p", monkeypatch, ASOF)
    from quantt.session import combine as cmb
    from quantt.session.tests.test_combine_noop import combinable
    # The live spec without `sizing_multiplier` (CEF trial 53): a combined book refuses that key
    # first (combine.py, ONE SIZING AUTHORITY PER BOOK), and this test is about missing_nav.
    sp = tmp_path / "live_combinable.frozen.json"
    sp.write_text(json.dumps(combinable(json.loads(LIVE_SPEC_PATH.read_text()))))
    bj = tmp_path / "book.json"
    bj.write_text(json.dumps({"book_id": "t", "sleeves": [
        {"name": "cef_discount", "enabled": True,
         "spec_path": sp.name, "risk_budget": 1.0}]}))
    sleeves = cmb.load_sleeves(bj, sp, tmp_path, rn._sleeve_target_fn)
    state = tmp_path / "state"
    state.mkdir()
    from quantt.session.tests.test_run import FakeClient
    out = _Quiet()
    deps = rn.Deps(client=FakeClient(state, clock_ts=EVE), env={"QUANTT_STATE_DIR": str(state)},
                   refresh=lambda a, t: rn.RefreshResult(exit=0, tail=""),
                   closes=lambda a, u: {}, navs=lambda a, u: {}, targets=lambda *a, **k: [],
                   halts=lambda: [], out=out, sleeves=sleeves, missing_nav=HOLD)
    assert rn.run_session(BOOK, SYN_SPEC, deps) == rn.EXIT_FAIL
    assert "built for the single-sleeve book" in "".join(out.text)


# ------------------------------------------- the age limit (team lead 2026-10-29)
#
# A POLICY of 2 consecutive sessions (book json data.missing_nav_max_sessions),
# not a measurement: prod's NAV panel (copy of 2026-10-28) shows no gap in 12
# months, because the vendor backfills dates and a late NAV survives only as a
# repeat. The count is read from the prior sessions' plan.json
# (run.missing_nav_streaks). Each test below fails on e0ad2d7, which holds for
# ever and reads no record.

PREV = dt.date(2026, 9, 25)          # the session before SESSION
PREV2 = dt.date(2026, 9, 24)
PREV3 = dt.date(2026, 9, 23)


def _limit_day(tmp_path, mp, label, prior, **kw):
    base, held = _synthetic_held(tmp_path / label, mp)
    _scenario_panel(base, tmp_path / label / "p", mp, ASOF, nav=(SYN_MISSING,))
    code, state, _, log = _session(tmp_path / label / "s", SYN_SPEC, held, FINAL, LATE_SCALE,
                                   refresh_exit=4, key=HOLD, prior=prior, **kw)
    return code, _plan(state), held, log


def _absent_refusals(tmp_path, mp):
    """Gate 5's refusals for the same day with the key absent: the limit's
    refusal must be these, plus one line."""
    base, held = _synthetic_held(tmp_path / "absent", mp)
    _scenario_panel(base, tmp_path / "absent" / "p", mp, ASOF, nav=(SYN_MISSING,))
    code, state, _, _ = _session(tmp_path / "absent" / "s", SYN_SPEC, held, FINAL, LATE_SCALE,
                                 refresh_exit=4)
    assert code == rn.EXIT_REFUSED
    return _plan(state)["refusals"]


def test_a_fund_is_held_within_the_age_limit(tmp_path, monkeypatch):
    """Without a dated NAV on the session before too: today is session 2 of 2, held."""
    code, plan, held, log = _limit_day(tmp_path, monkeypatch, "within", {
        PREV: _prior_plan(PREV, {SYN_MISSING: "2026-09-23"}), PREV2: _prior_plan(PREV2)})
    assert code == rn.EXIT_PLANNED, log
    _decided_with_hold(tmp_path / "within" / "s" / "state", held, SYN_MISSING,
                       len(SYN_TICKERS))
    rec = plan["missing_nav"]
    assert rec["held_before"] == {SYN_MISSING: 1} and rec["max_sessions"] == MAX_SESSIONS
    assert "session 2 of at most 2" in plan["targets"][SYN_MISSING]["reason"]


def test_the_day_after_the_age_limit_is_refused_as_without_the_key(tmp_path, monkeypatch):
    """Held on the two sessions before: the third refuses the WHOLE day, with gate
    5's refusals exactly as with the key absent, plus one line naming the fund and
    how long it has been held."""
    code, plan, _, log = _limit_day(tmp_path, monkeypatch, "over", {
        PREV: _prior_plan(PREV, {SYN_MISSING: "2026-09-23"}),
        PREV2: _prior_plan(PREV2, {SYN_MISSING: "2026-09-22"}), PREV3: _prior_plan(PREV3)})
    assert code == rn.EXIT_REFUSED, log
    assert plan["status"] == "refused" and plan["orders"] == []
    assert plan["refusals"][:-1] == _absent_refusals(tmp_path, monkeypatch)
    last = plan["refusals"][-1]
    assert last["gate"] == "data" and SYN_MISSING in last["detail"]
    assert "2 consecutive sessions" in last["detail"] and "max_sessions = 2" in last["detail"]
    rec = plan["missing_nav"]
    assert rec["action"] == "refused" and rec["held"] == [] and rec["held_before"] == \
        {SYN_MISSING: 2}


def test_the_count_resets_when_a_dated_nav_returns(tmp_path, monkeypatch):
    """Missing, then DATED, then missing: the count restarts and today is held.
    A key-off session that gate 5 passed also had every NAV dated. The control:
    two missing sessions in a row refuse."""
    code, plan, _, log = _limit_day(tmp_path, monkeypatch, "reset", {
        PREV: _prior_plan(PREV, {SYN_MISSING: "2026-09-23"}), PREV2: _prior_plan(PREV2),
        PREV3: _prior_plan(PREV3, {SYN_MISSING: "2026-09-21"})})
    assert code == rn.EXIT_PLANNED, log
    assert plan["missing_nav"]["held_before"] == {SYN_MISSING: 1}
    code, plan, _, log = _limit_day(tmp_path, monkeypatch, "keyoff", {
        PREV: _prior_plan(PREV, key_on=False)})
    assert code == rn.EXIT_PLANNED, log
    assert plan["missing_nav"]["held_before"] == {SYN_MISSING: 0}
    code, _, _, _ = _limit_day(tmp_path, monkeypatch, "control", {
        PREV: _prior_plan(PREV, {SYN_MISSING: "x"}), PREV2: _prior_plan(PREV2, {SYN_MISSING: "y"})})
    assert code == rn.EXIT_REFUSED


@pytest.mark.parametrize("label, prior, why", [
    ("absent", {}, "no plan.json for the session 2026-09-25"),
    ("garbage", {PREV: "{not json"}, "unreadable"),
    ("other_day", {PREV: _prior_plan(PREV2)}, "is not the record of the session 2026-09-25"),
    ("keyoff_data_refusal", {PREV: _prior_plan(PREV, key_on=False, refusals=[
        {"gate": "data", "detail": "refresh for as-of 2026-09-24 exited 4"}])},
     "the key was off and gate 5 refused"),
    ("no_missing_map", {PREV: {"session_date": "2026-09-25", "refusals": [],
                               "missing_nav": {"mode": "hold"}}}, "no `missing` mapping"),
    ("second_absent", {PREV: _prior_plan(PREV, {SYN_MISSING: "x"})},
     "no plan.json for the session 2026-09-24"),
])
def test_a_missing_or_unreadable_prior_record_refuses(tmp_path, monkeypatch, label, prior, why):
    """The count is never assumed: a record that is absent, unreadable, for another
    session, or silent about the fund refuses the day (team lead 2026-10-29)."""
    code, plan, _, log = _limit_day(tmp_path, monkeypatch, label, prior)
    assert code == rn.EXIT_REFUSED, log
    last = plan["refusals"][-1]["detail"]
    assert "cannot be counted" in last and why in last, last
    assert plan["missing_nav"]["action"] == "refused" and plan["orders"] == []


def test_the_count_survives_across_sessions_through_the_records(tmp_path, monkeypatch):
    """End to end, no hand-written record for the second day: the fund lacks its
    NAV for the as-of dates 09-24 and 09-25. Session 09-25 holds it (session 1)
    and writes its plan.json; session 09-28 reads that record, counts 1, and with
    a limit of 1 refuses."""
    base, held = _synthetic_held(tmp_path, monkeypatch)
    from src.deploy.sleeves import cef_discount as cefmod
    _scenario_panel(base, tmp_path / "p1", monkeypatch, ASOF, nav=(SYN_MISSING,))
    df = pd.read_parquet(cefmod.NAV_PATH)
    m = (pd.to_datetime(df["date"]) == pd.Timestamp(PREV2)) & (df["ticker"] == SYN_MISSING)
    assert int(m.sum()) == 1
    df[~m].reset_index(drop=True).to_parquet(cefmod.NAV_PATH)
    work = tmp_path / "s"
    day1 = dt.datetime(2026, 9, 25, 14, 30, 1, tzinfo=ET)
    code, state, _, log = _session(work, SYN_SPEC, held, day1, LATE_SCALE, refresh_exit=4,
                                   key=HOLD, asof=PREV2, session=PREV, max_sessions=1,
                                   prior={PREV2: _prior_plan(PREV2)})
    assert code == rn.EXIT_PLANNED, log
    p1 = _plan(state, PREV)
    assert p1["missing_nav"]["held"] == [SYN_MISSING] and p1["missing_nav"]["held_before"] == \
        {SYN_MISSING: 0}
    # Day 2 writes no prior of its own (prior={}): it must read day 1's real record.
    code, state, _, log = _session(work, SYN_SPEC, held, FINAL, LATE_SCALE, refresh_exit=4,
                                   key=HOLD, max_sessions=1, prior={})
    assert code == rn.EXIT_REFUSED, log
    p2 = _plan(state)
    assert p2["missing_nav"]["held_before"] == {SYN_MISSING: 1}
    assert "1 consecutive sessions" in p2["refusals"][-1]["detail"]


@pytest.mark.parametrize("data, want", [
    ({"stale_nav": "report"}, None),
    ({"missing_nav": "hold", "missing_nav_max_sessions": 2}, 2),
    ({"missing_nav": "hold", "missing_nav_max_sessions": 5, "_missing_nav_note": "x"}, 5)])
def test_the_age_limit_is_read_from_the_book_json(tmp_path, data, want):
    path = tmp_path / "book.json"
    path.write_text(json.dumps({"book_id": "b", "data": data}))
    assert rn.missing_nav_max_sessions_for(rn.Book("cef", "cef", Path("x"), path)) == want


@pytest.mark.parametrize("data", [
    {"missing_nav": "hold"},                                        # no default
    {"missing_nav": "hold", "missing_nav_max_sessions": 0},
    {"missing_nav": "hold", "missing_nav_max_sessions": -1},
    {"missing_nav": "hold", "missing_nav_max_sessions": True},
    {"missing_nav": "hold", "missing_nav_max_sessions": 2.0},
    {"missing_nav": "hold", "missing_nav_max_sessions": "2"},
    {"missing_nav": "hold", "missing_nav_max_sessions": None},
    {"stale_nav": "report", "missing_nav_max_sessions": 2},         # a limit for no hold
])
def test_an_age_limit_that_is_not_a_positive_int_raises(tmp_path, data):
    path = tmp_path / "book.json"
    path.write_text(json.dumps({"book_id": "b", "data": data}))
    with pytest.raises(rn.SessionError):
        rn.missing_nav_max_sessions_for(rn.Book("cef", "cef", Path("x"), path))


def test_the_key_without_its_age_limit_fails_the_session(tmp_path, monkeypatch):
    base, held = _synthetic_held(tmp_path, monkeypatch)
    code, _, _, log = _session(tmp_path / "s", SYN_SPEC, held, FINAL, LATE_SCALE,
                               refresh_exit=0, key=HOLD, max_sessions=None)
    assert code == rn.EXIT_FAIL and "missing_nav_max_sessions" in log
