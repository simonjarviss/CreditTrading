"""The combiner is DARK: the released book json decides byte-identically to de6e9c5.

WHAT IS PROVED (quantt/session/combine.py, OFF BY DEFAULT). With the book json
as released (one sleeve, `cef_discount`, no `risk_budget`), `load_sleeves`
returns None and the session takes the single-spec path; that path must give
the same targets, orders, plan.json and plan_sha as the code BEFORE the
combiner, de6e9c5 (release-20261028-1, what prod runs). Four tests:

  1. `test_the_released_book_json_takes_the_single_sleeve_path`: the released
     json, read by `load_sleeves` and by `default_deps` (broker client faked),
     gives `sleeves=None`. That is the bridge: tests 2 and 3 drive the session
     with `sleeves` absent, which is what None means.
  2. `test_synthetic_book_is_the_code_before_the_combiner` (NEVER SKIPS). A
     generated 13-fund panel (integer LCG and IEEE + - x / only, so the inputs
     are the same bytes on any machine; `panel` in the pin is their hash) and a
     fixture spec, decided as of 2026-09-25 on a flat and a held book, then the
     full session three ways: the late-market DECIDE, its SEND at 15:52:30 on
     the session date (armed, so orders go to the fake broker), and a `cls`
     evening run that decides and sends. Every output is hashed and compared
     with hashes COMPUTED BY de6e9c5's CODE. The generator and the fixture spec
     are copied from `test_c4_synthetic_pin.py` on branch `simon` (made for the
     same purpose at 66ec3df); the pins are this tree's own.
  3. `test_real_sleeve_on_the_real_panel_is_the_code_before_the_combiner`. The
     same on the real sleeve, a copy of the real panels' universe rows through
     2026-09-25 (the `test_nav_gate.py` and `test_c4_keys_noop.py` pattern:
     half the day-one book held, so the band trades and holds), and the core's
     spec AS IT WAS BEFORE CEF TRIAL 53 (cef_discount.v7.20260928), read from git
     at 35b429f (`pre_trial_spec`). Until 2026-11-01 this read the live spec,
     which then was v7. The activation made the live spec v8, and de6e9c5's code
     cannot run v8's `sizing_multiplier`, so the code-versus-code proof keeps
     v7. A pin is only a proof on the inputs it was made on, so the copy's
     content and that spec are hashed, and when either is not what the pin was
     made on, or git cannot show the spec, the test WARNS and skips, naming
     both. Test 2 is the one that never skips.
  3b. `test_real_sleeve_on_the_real_panel_live_spec_v9`: the same five outputs
     on the LIVE spec as released by CEF trial 53 amendment 1 (team lead
     2026-11-02): v9, with `sizing_multiplier` 1.30 applied. The pin was made on
     the amendment's tree (trial53-amend1), not on older code, so it is a
     regression pin of the released book. It is not a no-op proof: that is
     test 3, plus test_sizing_multiplier_noop.py. It FAILS, rather than skips,
     on any spec but v9 at x1.30. It also asserts that the live spec is the
     pre-trial spec plus the multiplier and nothing else, and that the
     multiplier acts (every weight target says `smult=1.3000`). Until the
     amendment it was a v8 pin at x1.13, made on 3478159, and it is in git at
     8b14298. v8's bytes are kept as `PINNED_INPUT_V8` / `v8_spec()` (git at
     862b1d0) for test_panels_noop's 862b1d0 pins.
  4. `test_one_sleeve_through_the_combiner_sends_what_the_single_sleeve_book_sends`,
     on the synthetic panel and (if present) the real one. Not a pin. It is a
     check of the combiner's arithmetic: the live spec as the only sleeve at
     risk_budget 1.0 must send the same orders, with the same plan_sha, as the
     single-sleeve path. plan.json differs only where it must: each target is a
     netted `qty`, every reason says which sleeve wanted it, and `combine` is
     added.

HOW THE PINS WERE MADE. `git archive de6e9c5` into a scratch directory (the
real `data/` symlinked in, read only), this file copied into that tree, and
`_hashes(_session(...))` run there: the synthetic pin unseeded and under
PYTHONHASHSEED 1, 2 and 3, the real-panel pin unseeded and under 1 (identical
every time); then on the combiner tree (identical again). To re-derive one --
after a deliberate change of the single-sleeve path, a pandas or numpy upgrade,
or a panel revision through 2026-09-25 -- do exactly that again and paste the
result; never edit a hash by hand.

SEED INDEPENDENCE. Where the sleeve's `max_gross_stress` BINDS on a held
book, its last ulp depends on the hash seed (the band's set union fixes the
order `_cap_gross` sums in; 11790b5's commit message, branch `simon`). It does
not bind on either held book here, and both tests assert so.

Hermetic: test_run's FakeClient for the broker, fixed clocks, no refresh, no
close-history reader (the pre-flight records UNMEASURED, a fixed string), and
the stale-NAV gate and the drawdown check off: their own report-mode proofs
(test_nav_gate.py, test_drawdown.py) compare off with report on this tree, so
with test 3 they carry over. netguard refuses any socket.
"""
import datetime as dt
import hashlib
import json
import platform
import warnings
from pathlib import Path

import pandas as pd
import pytest

from quantt.session import run as rn
from quantt.session.tests.test_run import BOOK, LATE, FakeClient
from src.deploy.registry import build_sleeve
from src.deploy.sleeve import SHORT, MarketState
from src.deploy.tests.test_group_cap import _fingerprint

ET = rn.gt.ET
ASOF = dt.date(2026, 9, 25)                                  # a Friday; plans for Monday 09-28
EVE = dt.datetime(2026, 9, 25, 22, 0, tzinfo=ET)
SEND = dt.datetime(2026, 9, 28, 15, 52, 30, tzinfo=ET)       # inside 15:52-15:58 ET
SESSION_DIR = "2026-09-28"
LIVE_SPEC_PATH = rn.REPO / "ops/specs/cef_discount.frozen.json"
# The core's spec before CEF trial 53 (cef_discount.v7.20260928), on origin/main, so every
# clone can show it. The revert tag spec-cef_discount.v7.20260928 names the same bytes, but it
# is local only, so the tests read the commit instead.
PRE_TRIAL_COMMIT = "35b429f"
TRIAL_KEYS = ("sizing_multiplier", "_sizing_multiplier_note")


class RealPanelPinNotApplicable(UserWarning):
    """The real-panel pin skipped: a bare skip shows one `s` under `-q`, so it
    also warns, and the warning lands in every run's summary (review of
    11790b5, branch `simon`)."""


class _Quiet:
    def write(self, s):
        return None

    def flush(self):
        return None


def _sha(x) -> str:
    return hashlib.sha256(x if isinstance(x, bytes) else x.encode()).hexdigest()


def pre_trial_spec() -> "tuple[bytes, dict] | None":
    """(raw bytes, parsed) of the core's frozen spec at PRE_TRIAL_COMMIT, or None when git
    cannot show it (no history: an archive, a shallow clone). The no-op pins made on older
    code read this, because that code cannot run trial 53's key."""
    import subprocess
    r = subprocess.run(["git", "-C", str(rn.REPO), "show",
                        f"{PRE_TRIAL_COMMIT}:ops/specs/cef_discount.frozen.json"],
                       capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    return r.stdout, json.loads(r.stdout)


def assert_live_is_pre_trial_plus_the_multiplier(pre: dict, live: dict):
    """The live spec is the pre-trial spec plus trial 53's key and its note, under a new id,
    and nothing else. A later spec change fails here; re-pin test 3b when that happens."""
    a, b = json.loads(json.dumps(pre)), json.loads(json.dumps(live))
    assert b["frozen"].get("sizing_multiplier") is not None, "the live spec has no multiplier"
    for k in TRIAL_KEYS:
        b["frozen"].pop(k, None)
    assert a["frozen"] == b["frozen"]
    for k in ("spec_id", "_supersedes", "description", "frozen"):
        a.pop(k), b.pop(k)
    assert a == b


def _real_panel_ready() -> bool:
    from src.deploy.sleeves import cef_discount as cefmod
    return cefmod.PX_PATH.exists() and cefmod.NAV_PATH.exists()


def _client(state, held, closes, clock_ts):
    c = FakeClient(state, positions=held, clock_ts=clock_ts)
    c.long_mv = sum(q * closes[s] for s, q in held.items() if q > 0)
    c.short_mv = sum(q * closes[s] for s, q in held.items() if q < 0)
    c.maint = 0.5 * (c.long_mv - c.short_mv)                 # fixture, not a measurement
    return c


def _deps(state, spec, client, execution, now, **extra):
    """The proofs' deps: the real readers on the sleeve's (patched) panel paths.
    `extra` is empty on de6e9c5; the combiner tree passes `sleeves=` in test 4."""
    from src.deploy.sleeves import cef_discount as cefmod
    cap = rn.spec_params(spec)["capital_usd"]
    return rn.Deps(
        client=client, env={"QUANTT_STATE_DIR": str(state), "DRY_RUN": "0"},
        refresh=lambda a, t: rn.RefreshResult(exit=0, tail="fixture"),
        closes=lambda a, u: rn.last_closes(cefmod.PX_PATH, a, u),
        navs=lambda a, u: rn.last_navs(cefmod.NAV_PATH, a, u),
        targets=lambda a, h, eq, op, **kw: rn.sleeve_targets(spec, cap, a, h, eq, op, **kw),
        halts=lambda: [], utcnow=lambda: now.astimezone(dt.timezone.utc),
        out=_Quiet(), execution=execution, **extra)


def _sent(client) -> list:
    """What reached the fake broker, in order: the wire fields."""
    return [[o["client_order_id"], o["symbol"], o["side"], o["qty"], o["time_in_force"]]
            for o in client.accepted.values()]


def _session(work, spec, **extra) -> dict:
    """The raw outputs of one as-of: the sleeve's day-one and held-book targets;
    a late-market DECIDE on the held book (evening), its SEND (15:52:30 on the
    session date, AUTO_ARMED); and a `cls` evening run, armed, that decides and
    sends. `work` is a fresh directory."""
    from src.deploy.sleeves import cef_discount as cefmod
    p = rn.spec_params(spec)
    cap, uni = p["capital_usd"], p["universe"]
    day1 = rn.sleeve_targets(spec, cap, ASOF, {}, cap, True)
    closes = {s: v[0] for s, v in rn.last_closes(cefmod.PX_PATH, ASOF, uni).items()}
    # Half the day-one book, so the band has trades to make and holds to keep.
    held = {t.instrument: int(0.5 * cap * float(t.weight) / closes[t.instrument])
            for t in day1 if t.weight}
    held = {s: q for s, q in held.items() if q}
    held_targets = rn.sleeve_targets(spec, cap, ASOF, held, cap, False)
    late = {**LATE, "bp_shortfall": "scale"}

    st = work / "late" / "state"
    st.mkdir(parents=True)
    code = rn.run_session(BOOK, spec, _deps(st, spec, _client(st, held, closes, EVE), late, EVE,
                                            **extra))
    plan_raw = (st / SESSION_DIR / "plan.json").read_bytes()
    (st / "AUTO_ARMED").touch()
    cs = _client(st, held, closes, SEND)
    send_code = rn.run_session(BOOK, spec, _deps(st, spec, cs, late, SEND, **extra))
    send_raw = (st / SESSION_DIR / "send.json").read_bytes()

    sc = work / "cls" / "state"
    sc.mkdir(parents=True)
    (sc / "AUTO_ARMED").touch()
    cc = _client(sc, held, closes, EVE)
    cls_code = rn.run_session(BOOK, spec, _deps(sc, spec, cc, {"mode": "cls",
                                                                "bp_shortfall": "scale"},
                                                EVE, **extra))
    cls_raw = (sc / SESSION_DIR / "plan.json").read_bytes()
    return {"day1": day1, "held_targets": held_targets, "exit": code, "plan_raw": plan_raw,
            "send_exit": send_code, "send_sent": _sent(cs), "send_raw": send_raw,
            "cls_exit": cls_code, "cls_sent": _sent(cc), "cls_raw": cls_raw}


def _hashes(r) -> dict:
    plan = json.loads(r["plan_raw"])
    return {"exit": r["exit"], "status": plan["status"], "n_orders": len(plan["orders"]),
            "band_holds": sum("band hold" in t["reason"] for t in plan["targets"].values()),
            "day_one_targets": _sha(_fingerprint(r["day1"])),
            "held_targets": _sha(_fingerprint(r["held_targets"])),
            "orders": _sha(json.dumps(plan["orders"], sort_keys=True)),
            "plan_targets": _sha(json.dumps(plan["targets"], sort_keys=True)),
            "plan_sha": plan["plan_sha"],
            "plan_json": _sha(r["plan_raw"]),
            "send_exit": r["send_exit"], "send_sent": _sha(json.dumps(r["send_sent"])),
            "send_json": _sha(r["send_raw"]),
            "cls_exit": r["cls_exit"], "cls_sent": _sha(json.dumps(r["cls_sent"])),
            "cls_plan_json": _sha(r["cls_raw"])}


def _assert_not_vacuous(r):
    """The sessions decided, sent and kept band holds, and the sleeve's gross cap
    did not bind on the held book (SEED INDEPENDENCE)."""
    plan = json.loads(r["plan_raw"])
    assert r["exit"] == rn.EXIT_PLANNED and plan["orders"]
    assert any("band hold" in t["reason"] for t in plan["targets"].values())
    assert r["send_exit"] == rn.EXIT_SENT and r["send_sent"]
    assert r["cls_exit"] == rn.EXIT_SENT and r["cls_sent"]
    assert not any("*x" in t.reason for t in r["held_targets"])


# -------------------------------------------------- 1. the released json is the old path

def test_the_released_book_json_takes_the_single_sleeve_path(monkeypatch):
    from quantt.session import combine as cmb
    b = rn.BOOKS["cef"]
    assert cmb.load_sleeves(b.book_path, b.spec_path, rn.REPO, rn._sleeve_target_fn) is None
    # And through default_deps, which main() builds (the broker client faked:
    # no key file is read).
    from quantt.broker import alpaca
    monkeypatch.setattr(alpaca.AlpacaClient, "from_environment",
                        classmethod(lambda cls, book, **kw: object()))
    deps = rn.default_deps(b, rn.load_spec(b.spec_path), {"QUANTT_ENV_FILE": "unused"})
    assert deps.sleeves is None
    # The released json: one sleeve, enabled, the book's own spec, no budget.
    book = json.loads(b.book_path.read_text())
    assert [(e["name"], e["enabled"], e["spec_path"], "risk_budget" in e)
            for e in book["sleeves"]] == [("cef_discount", True,
                                           "ops/specs/cef_discount.frozen.json", False)]


# -------------------------------------------------- 2. the synthetic pin (never skips)

SYN_TICKERS = tuple(f"SY{c}" for c in "ABCDEFGHIJKLM")
SYN_SPEC = {
    "spec_id": "synthetic.combiner-noop.v1", "status": "test", "capital_usd": 100_000.0,
    "allocation": {"type": "cef_discount"},
    "rebalance": {"min_trade_usd": 0.0},
    "risk": {"max_gross_exposure_usd": 260_000.0},
    "frozen": {"universe": list(SYN_TICKERS), "z_window": 252, "rebalance_days": 2,
               "vol_target_annual": 0.06, "min_adv_usd": 3_000_000.0, "max_nav_age_bd": 3,
               "min_names": 6, "min_abs_weight": 0.005, "gross_leverage": 1.0,
               "order_type": "MOC", "band_width": 0.048, "max_gross_stress": 1.8},
}
N_DAYS = 480
THIN = range(N_DAYS - 200, N_DAYS - 100)        # 8 names illiquid here: the flatten date's window
FLATTEN_I = N_DAYS - 101                        # 5 eligible, under min_names 6
FLATTEN_HELD = {"SYA": 1000.0, "SYF": -700.0}


def _lcg(seed: int):
    x = seed
    while True:
        x = (1103515245 * x + 12345) % 2147483648
        yield x


def _write_synthetic(dst):
    """The panel, in the live schema, at `dst`; returns (px_path, nav_path, dates, sha)."""
    dates = pd.bdate_range(end=pd.Timestamp(ASOF), periods=N_DAYS)
    px_rows, nav_rows = [], []
    for i, tk in enumerate(SYN_TICKERS):
        g = _lcg(20261027 + i)
        u = lambda: ((next(g) % 20001) - 10000) / 10000.0          # noqa: E731, in [-1, 1]
        level = -0.06 + 0.01 * i
        nav, d = 10.0 + i / 2.0, level
        for t, day in enumerate(dates):
            if t:
                nav = nav * (1.0 + 0.006 * u())
                d = 0.97 * d + 0.03 * level + 0.02 * u()
            if t >= N_DAYS - 40:                                     # today's z-scores spread
                d = d + (0.0005 if i % 2 else -0.0005)
            vol = 800_000 + next(g) % 400_001
            if i >= 5 and t in THIN:
                vol = 50_000
            if tk == "SYM" and t >= N_DAYS - 80:                     # illiquid on the decision date
                vol = 100_000
            px_rows.append({"date": day, "ticker": tk, "close": nav * (1.0 + d),
                            "volume": int(vol),
                            "grp": "muni" if i < 5 else ("hy", "loan", "multi")[i % 3]})
            if not (tk == "SYC" and t == N_DAYS - 3):                # a missing NAV row
                nav_rows.append({"date": day, "nav": nav, "ticker": tk})
    px, nv = dst / "cef_prices.parquet", dst / "cef_nav.parquet"
    P, N = pd.DataFrame(px_rows), pd.DataFrame(nav_rows)
    P.to_parquet(px)
    N.to_parquet(nv)
    return px, nv, dates, _sha(P.to_csv(index=False) + N.to_csv(index=False))


def _synthetic_sleeve(asof, holdings, opening):
    sl = build_sleeve(SYN_SPEC, SYN_SPEC["capital_usd"])
    ms = MarketState(asof=pd.Timestamp(asof), prices=pd.DataFrame(), holdings=dict(holdings),
                     extras={"sleeve_nav": SYN_SPEC["capital_usd"], "opening_session": opening})
    return sl.target_positions(pd.Timestamp(asof), ms)


def _half(day1, close):
    held = {}
    for t in day1:
        if t.weight:
            q = int(0.5 * SYN_SPEC["capital_usd"] * abs(float(t.weight)) / close[t.instrument])
            if q:
                held[t.instrument] = float(-q if t.side == SHORT else q)
    return held


def _synthetic_panel(tmp_path, monkeypatch):
    from src.deploy.sleeves import cef_discount as cefmod
    (tmp_path / "panel").mkdir()
    px, nv, dates, panel_sha = _write_synthetic(tmp_path / "panel")
    monkeypatch.setattr(cefmod, "PX_PATH", px)
    monkeypatch.setattr(cefmod, "NAV_PATH", nv)
    monkeypatch.setattr(cefmod, "GRP_PATH", px)
    return px, dates, panel_sha


def _synthetic_hashes(tmp_path, monkeypatch, reasons=None) -> dict:
    """Every output the pin covers, hashed: the sleeve on four dates (flat and
    held books), then `_session` as of ASOF. `reasons`, a dict if given,
    receives each book's reason strings (kept out of the hash)."""
    px, dates, panel_sha = _synthetic_panel(tmp_path, monkeypatch)
    P = pd.read_parquet(px)
    out = {"panel": panel_sha}
    for label, i in (("asof", N_DAYS - 1), ("asof-1", N_DAYS - 2), ("t-40", N_DAYS - 40),
                     ("flatten", FLATTEN_I)):
        day = dates[i]
        close = P[P["date"] == day].set_index("ticker")["close"].to_dict()
        day1 = _synthetic_sleeve(day, {}, True)
        held = _half(day1, close) if label != "flatten" else dict(FLATTEN_HELD)
        for b, targets in {"flat": day1, "held": _synthetic_sleeve(day, held, False)}.items():
            out[f"{label}|{b}"] = _sha(_fingerprint(targets))
            if reasons is not None:
                reasons[f"{label}|{b}"] = [t.reason for t in targets]
    r = _session(tmp_path / "run", SYN_SPEC)
    if reasons is not None:
        reasons["_session"] = r
    out.update(_hashes(r))
    return out


# WHICH ENTRIES ARE EXACT EVERYWHERE. The pin was made on an arm64 Mac; another
# CPU may differ in the last ulp of pandas rolling sums and numpy reductions,
# which only the `repr`-of-float target fingerprints can see. Everything else --
# whole-share orders, plan targets, plan.json and plan_sha, what was sent, the
# counts, the exits and the panel's own hash -- is integers and rounded text. So
# on the pin machine every entry must match; on any other the stable entries
# must match exactly (a change to what the book DECIDES still fails) and a moved
# float fingerprint is a warning naming the entries, never silent.
PIN_MACHINE = "arm64"
FLOAT_KEYS = frozenset({"asof|flat", "asof|held", "asof-1|flat", "asof-1|held",
                        "t-40|flat", "t-40|held", "flatten|flat", "flatten|held",
                        "day_one_targets", "held_targets"})

# PINNED 2026-10-28 on de6e9c5 (module docstring: how, and how to re-derive).
SYN_PINNED = {
    "asof-1|flat": "c96d532c3b5a9345fe87ea1f93d4a68724e8886532cb79fa0c373ad1c7fe2ae5",
    "asof-1|held": "5f3a3ae553dd0120c70bbfad6476dd464a3dd154e3daa96396635fd71d466f8f",
    "asof|flat": "919661d53041707542747ec84c0b5d6a358f8fb8aef3b65e3364a93bf42c5d71",
    "asof|held": "d8106417461bfa90b094ab4cfb0993f3bdc4b02fe8d674f07b07fffc965dc82b",
    "band_holds": 5,
    "cls_exit": 0,
    "cls_plan_json": "92d11e888ceafa44614f3f01067fe5a0ab65dd8f424c4da083ec70cb57f61e02",
    "cls_sent": "6e4f097e25d3baddfa5d4beda0c51ff007eda0d6e421dee51208892b8baa48ff",
    "day_one_targets": "919661d53041707542747ec84c0b5d6a358f8fb8aef3b65e3364a93bf42c5d71",
    "exit": 6,
    "flatten|flat": "d7476eddef84cf9172a80137dd6bb810d8208773ddc0c3d6b3c779e8c3a173f1",
    "flatten|held": "d7476eddef84cf9172a80137dd6bb810d8208773ddc0c3d6b3c779e8c3a173f1",
    "held_targets": "d8106417461bfa90b094ab4cfb0993f3bdc4b02fe8d674f07b07fffc965dc82b",
    "n_orders": 7,
    "orders": "e628eb451ee60ed44c2a3432437a51e54f7759a97439d112ce119d11e3271024",
    "panel": "172d57548229a8776518927875787e15e3c5476f9e57cd9df99e90c78738b277",
    "plan_json": "329a99ae4129552a3fa5b10fd9e7ffe82a82155823d0e706d9dbfd7f4e2e61c2",
    "plan_sha": "aa3cc8b1827344eac6a143892be4faa969df5bcb1431b09903b93b8c229a780e",
    "plan_targets": "732894a285fe4821a443ae4ce9d9d609cc3e382edc831ccb239c03e155f5fb6f",
    "send_exit": 0,
    "send_json": "28900ab87d89f8716cc885b35b3612f9f9b33ca0be117b85d12659cbd5624819",
    "send_sent": "5409c95d63e197ab80437a44fa71fb69e234f2578348b84b75cc9217193f6aaf",
    "status": "decided",
    "t-40|flat": "cb20ef6940fb809c4c06cadf7200e74798f28fd60546e30fcaa0496b2bde9553",
    "t-40|held": "92174d671ec1ff2cd7d113c89be4458df8dcaa2ac408a5c9a1e7c16c5db6ca86",
}


def _compare(got: dict, pinned: dict, what: str):
    assert FLOAT_KEYS & set(pinned) and set(got) == set(pinned)
    if platform.machine() == PIN_MACHINE:
        assert got == pinned
        return
    stable = {k: v for k, v in pinned.items() if k not in FLOAT_KEYS}
    assert {k: got[k] for k in stable} == stable
    moved = sorted(k for k in FLOAT_KEYS & set(pinned) if got[k] != pinned[k])
    if moved:
        warnings.warn(f"{what}: float fingerprints {moved} differ on {platform.machine()} from "
                      f"the {PIN_MACHINE} pin; the orders, plan and counts match exactly. "
                      f"Re-derive on this machine per the module docstring if this platform "
                      f"should be pinned too.")


def test_synthetic_book_is_the_code_before_the_combiner(tmp_path, monkeypatch):
    reasons = {}
    got = _synthetic_hashes(tmp_path, monkeypatch, reasons)
    _compare(got, SYN_PINNED, "combiner synthetic pin")
    # Not vacuous: the branches the generator was built to reach are reached.
    every = [x for k, rs in reasons.items() if k != "_session" for x in rs]
    assert any("band hold" in x for x in every) and any("cef discount z=" in x for x in every)
    assert any("illiquid" in x for x in every) and any("below min weight" in x for x in every)
    assert set(reasons["flatten|held"]) == {"cef: only 5 eligible names"}
    assert not any("*x" in x for x in reasons["asof|held"])
    _assert_not_vacuous(reasons["_session"])


# -------------------------------------------------- 3. the real-panel pin

def _frozen_copy(dst, monkeypatch, universe) -> str:
    """Copy the real panels' rows for `universe` dated at or before ASOF into
    `dst`, sorted (ticker, date) with a stable sort, point the sleeve at the copy,
    and return the sha256 of its canonical content. Rows after ASOF and other
    tickers cannot reach a decision as of ASOF, but they change with every
    refresh; the copy keeps the pin's input exactly the rows the decision reads."""
    from src.deploy.sleeves import cef_discount as cefmod
    parts, paths = [], {}
    for name, src in (("cef_prices.parquet", cefmod.PX_PATH), ("cef_nav.parquet", cefmod.NAV_PATH)):
        df = pd.read_parquet(src)
        df = df[df["ticker"].isin(universe) & (pd.to_datetime(df["date"]) <= pd.Timestamp(ASOF))]
        df = df.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
        paths[name] = dst / name
        df.to_parquet(paths[name])
        parts.append(f"{name}\n{sorted((c, str(t)) for c, t in df.dtypes.items())}\n"
                     f"{df.to_csv(index=False)}")
    monkeypatch.setattr(cefmod, "PX_PATH", paths["cef_prices.parquet"])
    monkeypatch.setattr(cefmod, "NAV_PATH", paths["cef_nav.parquet"])
    monkeypatch.setattr(cefmod, "GRP_PATH", paths["cef_prices.parquet"])
    return _sha("\n".join(parts))


# PINNED 2026-10-28 on de6e9c5, on the laptop's dev panels (cef_prices to
# 2026-10-15, cef_nav to 2026-10-14; only rows through ASOF are read).
PINNED_INPUT = {
    "panel": "3c614b42a0acf9ea570afba16f2c4defd990799a8c231d9cdd0c71f5daebcc7a",
    "spec": "c05035e55eaa89172f65d38a3485cb1c68123217177343b38576edf56583c02e",
}
PINNED = {
    "band_holds": 6,
    "cls_exit": 0,
    "cls_plan_json": "30c8365833d800354de21de157fa01b62e4eeb90674400583fc756639ac36e6c",
    "cls_sent": "25b99647c913c17a63ddf53de40eb555ee25068c6c3e0b9e2851053e0e698638",
    "day_one_targets": "191edf1e76de87eb654a62068e69e1e250fffa9a64c6c19d8bbf1d99676f7d70",
    "exit": 6,
    "held_targets": "c7107831e64c5968dda563d267c23a5c631168cb5525f1d60fbadd0b761f70eb",
    "n_orders": 6,
    "orders": "f198dd92f1f473578190d104e61bd70d8bb2352ecb253bc12ccc6c9b23d75a2c",
    "plan_json": "410f7a4d24f97f08f533d8afe4c07736f277128816554474e19d8e74c9977fb8",
    "plan_sha": "e69a46f6680840664ed3b44e21eb767cf4d9f641e0b3f9ee0fd07e45fa084e05",
    "plan_targets": "978e2df32387f0be9e49a3a5966369bed1866e780b1ca8d79d562d11f2c37f56",
    "send_exit": 0,
    "send_json": "ac1adb88597ac75eb557fc634eae9f879b5196a07c03cdbbcfc05fa2a46d6a9b",
    "send_sent": "b30cc665d139dfebf931d9cac73299e66c22518a92a49e5c70d6a68e9532139d",
    "status": "decided",
}


@pytest.mark.skipif(not _real_panel_ready(), reason="real CEF panels absent (data/ is "
                                                     "gitignored); the synthetic pin still runs")
def test_real_sleeve_on_the_real_panel_is_the_code_before_the_combiner(tmp_path, monkeypatch):
    from src.deploy.sleeves import cef_discount as cefmod
    real = {f: f.read_bytes() for f in (cefmod.PX_PATH, cefmod.NAV_PATH)}
    pre = pre_trial_spec()
    if pre is None:
        why = (f"REAL-PANEL COMBINER NO-OP PIN NOT APPLIED: git cannot show "
               f"{PRE_TRIAL_COMMIT}:ops/specs/cef_discount.frozen.json, the spec the pin was made on")
        warnings.warn(why, RealPanelPinNotApplicable)
        pytest.skip(why)
    raw, spec = pre
    (tmp_path / "panels").mkdir()
    got_input = {"panel": _frozen_copy(tmp_path / "panels", monkeypatch,
                                       spec["frozen"]["universe"]),
                 "spec": _sha(raw)}
    if got_input != PINNED_INPUT:
        why = (f"REAL-PANEL COMBINER NO-OP PIN NOT APPLIED: it was made on panel/spec "
               f"{PINNED_INPUT}; this tree has {got_input} (a refresh revised rows through "
               f"{ASOF}, another machine's panel, or a spec bump). The old code's output on "
               f"these inputs is unmeasured; the synthetic pin still runs")
        warnings.warn(why, RealPanelPinNotApplicable)
        pytest.skip(why)
    assert cefmod.PX_PATH.parent == tmp_path / "panels"            # deciding on the copy
    r = _session(tmp_path / "run", spec)
    _compare(_hashes(r), PINNED, "combiner real-panel pin")
    _assert_not_vacuous(r)
    assert all(f.read_bytes() == b for f, b in real.items()), "a real panel changed"


# -------------------------------------------------- 3b. the live spec as released (v9)

# The core's spec as RELEASED BEFORE amendment 1 (cef_discount.v8.20261101, release-20261102-1 at
# 862b1d0, on origin/main). test_panels_noop's 862b1d0 pins were made on it, and read it here so
# they survive the v9 activation. The local tag spec-cef_discount.v8.20261101 names the same bytes.
V8_COMMIT = "862b1d0"
# The v8 input those pins were made on (the same panel copy as test 3; v8's sha).
PINNED_INPUT_V8 = {
    "panel": PINNED_INPUT["panel"],
    "spec": "b9259d70c11d2ecfc1011a953e328e22c325bc34fc2a48318ffb502e0c0d3cd5",
}


def v8_spec() -> "tuple[bytes, dict] | None":
    """(raw bytes, parsed) of the core's spec at V8_COMMIT, or None when git cannot show it."""
    import subprocess
    r = subprocess.run(["git", "-C", str(rn.REPO), "show", f"{V8_COMMIT}:ops/specs/cef_discount.frozen.json"],
                       capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    return r.stdout, json.loads(r.stdout)


# The live spec as released by CEF trial 53 amendment 1 (team lead 2026-11-02): v9, x1.30.
LIVE_ID, LIVE_M = "cef_discount.v9.20261102", 1.3


def _live(tmp_path, monkeypatch):
    """(input, raw outputs, live spec) of test 3's five outputs on the LIVE spec."""
    raw = LIVE_SPEC_PATH.read_bytes()
    spec = json.loads(raw)
    (tmp_path / "panels").mkdir()
    got_input = {"panel": _frozen_copy(tmp_path / "panels", monkeypatch,
                                       spec["frozen"]["universe"]),
                 "spec": _sha(raw)}
    return got_input, (_session(tmp_path / "run", spec) if got_input == PINNED_INPUT_V9 else None), spec


def print_live_pin():
    """Print test 3b's pin (module docstring, 3b): run on the release tree, never edited by hand."""
    import tempfile
    with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
        got_input, r, _ = _live(Path(d), mp)
        print("input", got_input)
        print("PINNED_V9 =", json.dumps(_hashes(r) if r else None, indent=1, sort_keys=True))


# PINNED 2026-11-02 on trial53-amend1 (8b14298 plus amendment 1's v9 spec and this file), on the
# laptop's dev panels (cef_prices to 2026-10-15, cef_nav to 2026-10-14; only rows through ASOF are
# read). The live spec is cef_discount.v9.20261102: the pre-trial spec plus sizing_multiplier 1.30.
# Until amendment 1 this was a v8 pin at x1.13 (PINNED_V8, in git at 8b14298).
# RE-PINNED 2026-11-11, input only: a note-only edit (team lead 2026-11-11, no spec_id bump) made
# `frozen._sizing_multiplier_note` also name scripts/cef/exposure_readout.py. The file's sha256 moved
# from dd92e06d814a... and no value moved. PINNED_V9 below is unchanged and still matches. Without
# the re-pin this test would skip, with a warning, instead of comparing.
PINNED_INPUT_V9 = {
    "panel": PINNED_INPUT["panel"],
    "spec": "555286d0659cd69dd4a5e5c98e16e4f64e089db1ac0d2605baec20e5917bb777",
}
# Identical unseeded and under PYTHONHASHSEED 1 and 2.
PINNED_V9 = {
 "band_holds": 6,
 "cls_exit": 0,
 "cls_plan_json": "13cf21aeea16c7e7f90ed28c5b19f5e351115e636855de3bd93cd61eccf13579",
 "cls_sent": "c7abedb293ac6711b6acedb4f0c10f723478d2c8e08f9d2ca6793059929a7e1d",
 "day_one_targets": "4e001f8f0e557d14ff643cf11bd7cfbb5f8aa7e819121805f636a04d66d7a0a7",
 "exit": 6,
 "held_targets": "4b555dcfff8b3bbf16b4972344d574ad25ee35ea2a57d0c9cdc100bc69757379",
 "n_orders": 6,
 "orders": "43047d3746b9b7af657653bc7750be1bfd9b10cb894cb07f32d5a0d35d35f316",
 "plan_json": "b2c7e93fddd497ce0a2b0eb5e05be17bffe7d334c7058b2292523cfa20faf699",
 "plan_sha": "5492fb8b0b83ff766cbeba4d101429d7c3bb74fb38d70321c8b99f74987dbcd6",
 "plan_targets": "0f9d957fa4f1c107c95b100ecd3f9b70a8f724cff2fd0097750a080f0995bb6a",
 "send_exit": 0,
 "send_json": "da634201e75bc81f15745da4c517dad67a10501462721b98ab004b880ad726c1",
 "send_sent": "4346b2811ae0fa9dcf7cde81487ee03b84fcbd706463d0b41be30123ce25d706",
 "status": "decided"
}


@pytest.mark.skipif(not _real_panel_ready(), reason="real CEF panels absent (data/ is "
                                                     "gitignored); the synthetic pin still runs")
def test_real_sleeve_on_the_real_panel_live_spec_v9(tmp_path, monkeypatch):
    from src.deploy.sleeves import cef_discount as cefmod
    real = {f: f.read_bytes() for f in (cefmod.PX_PATH, cefmod.NAV_PATH)}
    live = json.loads(LIVE_SPEC_PATH.read_text())
    # The released spec IS amendment 1's: this fails (it does not skip) on any other spec, so a
    # spec change cannot leave this pin silently unapplied. Re-pin with print_live_pin().
    assert (live["spec_id"], live["frozen"].get("sizing_multiplier")) == (LIVE_ID, LIVE_M)
    pre = pre_trial_spec()
    got_input, r, live = _live(tmp_path, monkeypatch)
    if r is None:
        why = (f"REAL-PANEL LIVE-SPEC (v9) PIN NOT APPLIED: it was made on panel/spec "
               f"{PINNED_INPUT_V9}; this tree has {got_input} (a refresh revised rows through "
               f"{ASOF}, or another machine's panel). Re-pin with print_live_pin(); test 3 and "
               f"the synthetic pins still run")
        warnings.warn(why, RealPanelPinNotApplicable)
        pytest.skip(why)
    if pre is not None:
        assert_live_is_pre_trial_plus_the_multiplier(pre[1], live)
    m = live["frozen"]["sizing_multiplier"]
    for t in r["day1"]:
        if t.weight:
            assert f"smult={m:.4f}" in t.reason, t.reason       # the multiplier acts
    _compare(_hashes(r), PINNED_V9, "live-spec (v9) real-panel pin")
    plan = json.loads(r["plan_raw"])
    assert r["exit"] == rn.EXIT_PLANNED and plan["orders"]
    assert r["send_exit"] == rn.EXIT_SENT and r["cls_exit"] == rn.EXIT_SENT
    assert all(f.read_bytes() == b for f, b in real.items()), "a real panel changed"


# -------------------------------------------------- 4. one sleeve through the combiner

def _one_sleeve(tmp_path, spec_path, repo):
    """The combiner engaged on ONE sleeve, the book's own spec, at budget 1.0."""
    from quantt.session import combine as cmb
    bj = tmp_path / "book.json"
    bj.write_text(json.dumps({"book_id": "t", "sleeves": [
        {"name": "cef_discount", "enabled": True,
         "spec_path": spec_path.relative_to(repo).as_posix(), "risk_budget": 1.0}]}))
    sleeves = cmb.load_sleeves(bj, spec_path, repo, rn._sleeve_target_fn)
    assert sleeves is not None and len(sleeves) == 1
    return sleeves


def _assert_same_trades(single: dict, combined: dict, budget_nav: float):
    a, b = json.loads(single["plan_raw"]), json.loads(combined["plan_raw"])
    wire = ("client_order_id", "symbol", "side", "qty", "time_in_force", "leg", "current",
            "target", "est_price")
    assert [{k: o[k] for k in wire} for o in a["orders"]] == \
        [{k: o[k] for k in wire} for o in b["orders"]]
    assert a["plan_sha"] == b["plan_sha"]
    assert {s: (t["current"], t["target"]) for s, t in a["targets"].items()} == \
        {s: (t["current"], t["target"]) for s, t in b["targets"].items()}
    for k in ("exit", "send_exit", "send_sent", "cls_exit", "cls_sent"):
        assert single[k] == combined[k], k
    assert json.loads(single["send_raw"])["plan_sha"] == json.loads(combined["send_raw"])["plan_sha"]
    # Where plan.json must differ, and only there.
    assert "combine" not in a
    c = b.pop("combine")
    for x in (a, b):
        for o in x["orders"]:
            o.pop("reason")
        for t in x["targets"].values():
            t.pop("reason")
            t.pop("kind")
    assert a == b
    rec = c["sleeves"]["cef_discount"]
    assert rec["sleeve_nav"] == budget_nav and rec["status"] == "decided"
    assert {s: t["target"] for s, t in rec["targets"].items()} == \
        {s: t["target"] for s, t in json.loads(single["plan_raw"])["targets"].items()}


def test_one_sleeve_through_the_combiner_sends_what_the_single_sleeve_book_sends(
        tmp_path, monkeypatch):
    _synthetic_panel(tmp_path, monkeypatch)
    sp = tmp_path / "syn.frozen.json"
    sp.write_text(json.dumps(SYN_SPEC))
    single = _session(tmp_path / "single", SYN_SPEC)
    combined = _session(tmp_path / "combined", SYN_SPEC,
                        sleeves=_one_sleeve(tmp_path, sp, tmp_path))
    _assert_not_vacuous(single)
    _assert_same_trades(single, combined, budget_nav=100_000.0)


def combinable(spec: dict) -> dict:
    """The spec with `sizing_multiplier` and its note removed (CEF trial 53, 2026-11-01).

    A combined book refuses the key (quantt/session/combine.py, ONE SIZING AUTHORITY PER
    BOOK), so since the live spec carries it (cef_discount.v8.20261101) the combiner's tests
    on the live spec take it without the key. Everything else is the live spec's."""
    s = json.loads(json.dumps(spec))
    s["frozen"].pop("sizing_multiplier", None)
    s["frozen"].pop("_sizing_multiplier_note", None)
    return s


@pytest.mark.skipif(not _real_panel_ready(), reason="real CEF panels absent (data/ is "
                                                     "gitignored); the synthetic version runs")
def test_one_sleeve_through_the_combiner_on_the_real_panel(tmp_path, monkeypatch):
    from quantt.session import combine as cmb
    live = json.loads(LIVE_SPEC_PATH.read_text())
    if "sizing_multiplier" in live["frozen"]:          # refused as it stands (one sizing authority)
        (tmp_path / "refused").mkdir()
        with pytest.raises(cmb.CombineError, match="sizing_multiplier"):
            _one_sleeve(tmp_path / "refused", LIVE_SPEC_PATH, rn.REPO)
    spec = combinable(live)
    sp = tmp_path / "live_combinable.frozen.json"
    sp.write_text(json.dumps(spec))
    (tmp_path / "panels").mkdir()
    _frozen_copy(tmp_path / "panels", monkeypatch, spec["frozen"]["universe"])
    single = _session(tmp_path / "single", spec)
    combined = _session(tmp_path / "combined", spec,
                        sleeves=_one_sleeve(tmp_path, sp, tmp_path))
    _assert_not_vacuous(single)
    _assert_same_trades(single, combined, budget_nav=100_000.0)
