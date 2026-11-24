"""`level_signal` (CEF trial 54): absent is C4's v4 book byte for byte; present is §1.2 exactly.

results/cef/PREREG_C4_LEVEL_2026-11-02.md §1, approved by the team lead 2026-11-03. With the key
set, C4's UNIT target is an equal-risk blend of its z target and a within-family discount-level
target, through the same vol scalar, multiplier, band and 1.90 gross cap
(src/deploy/sleeves/cef_discount.py, module docstring; `_level_weights`, `_blend_unit_book`).

THE NO-OP (§1.3 test 1), against the code BEFORE the key, f7f7be5 (origin/main when this branch
was cut; C4's spec there is c4_families.v4.20261102), and against 4485a96 (origin/main when it was
merged in, 2026-11-03; the same sleeve and spec, a newer runner):
  1. `test_key_absent_targets_are_f7f7be5s` NEVER SKIPS. The sleeve on a generated 74-fund C4
     panel, on C4's live spec with `level_signal` and its note removed (asserted to leave v4's
     frozen block, byte for byte), on a flat book and a held book at three dates. Every target's
     fingerprint (repr floats, reasons, meta) is hashed, in full and with floats to 10 significant
     digits, and compared with hashes computed by f7f7be5's code (and by 4485a96's: identical).
  2. `test_key_absent_session_is_f7f7be5s`: a full C4 session through `run_session` on that
     panel with C4's v4 spec (the live file while it is v4, else `git show f7f7be5:...`, so the
     proof survives the activation): plan.json, plan_sha, orders, targets and the run record of
     the evening decide, and the run record of the 15:52 send, against 4485a96's runner. Skips,
     warning, only when neither source gives v4's bytes.
  ON OTHER CPUs (`_check_pins`, test_combine_noop's rule). The pins were made on an arm64 Mac. CI's
  x86 moves the last ulp of the repr fingerprints, plan.json and the run records (seen on the CI run
  of 3b4c963), so those are exact on the pin machine only and a warning elsewhere; every other entry
  (the rounded fingerprints, orders, plan_sha, plan targets, counts, exits) must match everywhere.
  HOW THE PINS WERE MADE: `git archive <commit>` into a scratch directory, this file copied into
  that tree, `print_pins()` run there unseeded and under PYTHONHASHSEED 1 and 2 (identical every
  time); then on this tree (identical again). Never edit a hash by hand. Both pass on the old code by
  construction: they are no-op proofs. The real-panel proof (the last 10 dates of the core's and
  C4's panels, both specs) is in the commit messages.

WHAT THE KEY DOES. Each test below fails on f7f7be5 (shown before it was kept; the commit
message says how each fails):
  3. the blend is §1.2's construction, against an independent numpy re-derivation from the
     sleeve's own eligible names, discount and prices (to 1e-12), with C4's masks and ADV floor
     applied to the level as to the z;
  4. a family with one ELIGIBLE name contributes zero level weight (a singleton family, and a
     pair whose other member is illiquid: the family mean is over eligible names only);
  5. a ticker missing from family_of raises, naming it: at load, at construction, and in
     `_level_weights` for an eligible name;
  6. the blend reads nothing after t: every row after t perturbed leaves t's targets
     byte-identical, and the alignment check refuses returns past the signal date;
  7. the risk_share -> 1 limit (reachable only through a test patch: the key refuses 1.0) is
     the z book;
  8. the cap still binds at max_gross_stress / m in unit weights, so the emitted gross is at
     most max_gross_stress x NAV (both read from C4's spec, never written here);
  9. equal risk: at risk_share 0.5 the two parts' standalone vols and Euler risk contributions
     are equal to 1e-12, on returns with known vols;
 10. the registry refuses every malformed value, a near-miss spelling and the key without a band.

Synthetic data throughout: every conclusion is about this code, never about a market.
"""
import copy
import datetime as dt
import hashlib
import json
import math
import platform
import re
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quantt.session import run as rn
from src.deploy import registry
from src.deploy.sleeve import SHORT, MarketState
from src.deploy.sleeves import cef_discount as cefmod
from src.deploy.sleeves.cef_discount import CEFDiscountSleeve
from src.deploy.tests.test_group_cap import _fingerprint

C4_SPEC = rn.REPO / "ops" / "specs" / "c4_families.frozen.json"
FAMILIES = rn.REPO / "results" / "cef" / "c4" / "c4_universe_frozen_2026-10-14.csv"
BASE_COMMIT = "f7f7be5"            # the code before the key (the target pins)
SESSION_BASE = "4485a96"           # origin/main merged in: the runner the session pins were made on
# sha256 of C4's spec file at BASE_COMMIT (c4_families.v4.20261102), and of its `frozen` block
# as canonical JSON (sort_keys, no spaces): what "the key absent" must leave.
# RE-PINNED 2026-11-11 for a note-only edit (team lead 2026-11-11: edit the note, regenerate C4's
# artifacts, no spec_id bump): `frozen._sizing_multiplier_note` now also names
# scripts/cef/exposure_readout.py. No value moved. v4's own frozen block hashed to 59a4c00d6d60...;
# this is that block with the one note edited. The target pins below did not move.
V4_FILE_SHA = "a419959d38d2a2447593ea3f4f4ce308216461fa30efe3f7af5a5809687064b3"
V4_FROZEN_SHA = "d781e41ed07dd57b0e8457733a64fe5ea72292cb3d5e0c4d137fd29b970c0d13"
TRIAL_KEYS = ("level_signal", "_level_signal_note")

ASOF = dt.date(2026, 9, 25)                  # test_c4_book's as-of: the session is Monday 09-28
N_DAYS = 400
ILLIQUID = "GAM"                             # equity_domestic; illiquid over the last 80 sessions
M1_TODAY = "BDJ"                             # its NAV on ASOF repeats the previous row (M1)
M2_TODAY = "DFP"                             # zero volume on ASOF (M2)
PIN_DATES = (N_DAYS - 1, N_DAYS - 2, N_DAYS - 31)


class LevelPinNotApplicable(UserWarning):
    """The session pin skipped: neither the live file nor git gave v4's bytes."""


def _sha(x) -> str:
    return hashlib.sha256(x if isinstance(x, bytes) else x.encode()).hexdigest()


def _canon(d) -> str:
    return json.dumps(d, sort_keys=True, separators=(",", ":"))


def _families() -> dict:
    """{ticker: family} for the 74, from the frozen CSV C4's spec copies (column `family`)."""
    fz = pd.read_csv(FAMILIES)
    return dict(zip(fz["ticker"], fz["family"]))


def _lcg(seed: int):
    x = seed
    while True:
        x = (1103515245 * x + 12345) % 2147483648
        yield x


def _write_panel(root: Path) -> str:
    """A generated panel for the 74 frozen funds at root/data/cef_c4/, in the live schema
    (integer LCG and IEEE + - x / only, so the bytes are the same on any machine). Each fund's
    discount mean-reverts to its own level (a family base plus a per-fund offset that persists:
    rich and cheap funds inside each family), so the level and the z disagree. Returns the
    hash of the rows. It reaches: ILLIQUID dropped by the ADV floor, M1_TODAY masked by a NAV
    repeat on ASOF, M2_TODAY masked by zero volume on ASOF, NAV repeats in the z history."""
    fam = _families()
    base = {f: -0.12 + 0.03 * k for k, f in enumerate(sorted(set(fam.values())))}
    dates = pd.bdate_range(end=pd.Timestamp(ASOF), periods=N_DAYS)
    px, nv = [], []
    for i, tk in enumerate(sorted(fam)):
        g = _lcg(20261103 + i)
        u = lambda: ((next(g) % 20001) - 10000) / 10000.0          # noqa: E731, in [-1, 1]
        level = base[fam[tk]] + 0.004 * ((i * 7) % 11 - 5)
        nav, d = 10.0 + (i % 17) / 2.0, level
        prev_nav = nav
        for t, day in enumerate(dates):
            if t:
                prev_nav = nav
                nav = nav * (1.0 + 0.006 * u() + 0.0001)
                d = 0.97 * d + 0.03 * level + 0.015 * u()
            if t % 37 == (i % 37) and t > 0:                       # an occasional repeated NAV
                nav = prev_nav
            if tk == M1_TODAY and t == N_DAYS - 1:
                nav = prev_nav
            vol = int(800_000 + next(g) % 400_001)
            if tk == ILLIQUID and t >= N_DAYS - 80:
                vol = 10_000
            if tk == M2_TODAY and t == N_DAYS - 1:
                vol = 0
            c = nav * (1.0 + d)
            px.append({"date": day, "open": c, "high": c, "low": c, "close": c, "volume": vol,
                       "ticker": tk, "grp": fam[tk]})
            nv.append({"date": day, "nav": nav, "ticker": tk})
    dst = root / "data" / "cef_c4"
    dst.mkdir(parents=True, exist_ok=True)
    P, N = pd.DataFrame(px), pd.DataFrame(nv)
    P.to_parquet(dst / "cef_prices.parquet")
    N.to_parquet(dst / "cef_nav.parquet")
    return _sha(P.to_csv(index=False) + N.to_csv(index=False))


def _use_root(root: Path, mp):
    """`root` stands in for the repository root: C4's panel_source resolves under it, and the
    core's data/cef/ files are absent there, so any read of them raises."""
    mp.setattr(cefmod, "REPO", root)
    for name in ("PX_PATH", "NAV_PATH", "GRP_PATH"):
        mp.setattr(cefmod, name, root / "data" / "cef" / "absent.parquet")
    mp.setitem(rn.DATA_BOOK_DIRS, "c4", root / "data" / "cef_c4")


def _panel(tmp_path, mp) -> tuple[Path, str, pd.DatetimeIndex]:
    root = tmp_path / "repo"
    sha = _write_panel(root)
    _use_root(root, mp)
    return root, sha, pd.bdate_range(end=pd.Timestamp(ASOF), periods=N_DAYS)


def _live_spec() -> dict:
    return json.loads(C4_SPEC.read_text())


def _absent_spec() -> dict:
    """C4's live spec with trial 54's key and note removed: v4's frozen block, if the
    activation moved nothing else (`test_key_absent_targets_are_f7f7be5s` asserts it)."""
    s = _live_spec()
    for k in TRIAL_KEYS:
        s["frozen"].pop(k, None)
    return s


def _with_level(spec: dict, risk_share=0.5, family_of=None) -> dict:
    s = copy.deepcopy(spec)
    s["frozen"]["level_signal"] = {"risk_share": risk_share,
                                   "family_of": _families() if family_of is None else family_of}
    return s


def _ms(day, held=(), opening=None, nav=None):
    cap = float(_live_spec()["capital_usd"])
    held = dict(held)
    return MarketState(asof=pd.Timestamp(day), prices=pd.DataFrame(), holdings=held,
                       extras={"sleeve_nav": cap if nav is None else nav,
                               "opening_session": (not held) if opening is None else opening})


def _targets(spec, day, held=()):
    sl = registry.build_sleeve(spec, float(spec["capital_usd"]))
    return sl.target_positions(pd.Timestamp(day), _ms(day, held))


def _closes(root: Path, day) -> dict:
    P = pd.read_parquet(root / "data" / "cef_c4" / "cef_prices.parquet")
    P = P[pd.to_datetime(P["date"]) == pd.Timestamp(day)]
    return dict(zip(P["ticker"], P["close"].astype(float)))


def _half(targets, closes, cap) -> dict:
    """Whole shares of half the day-one book at the date's closes (the band trades and holds)."""
    out = {}
    for t in targets:
        if t.weight:
            q = int(0.5 * cap * abs(float(t.weight)) / closes[t.instrument])
            if q:
                out[t.instrument] = float(-q if t.side == SHORT else q)
    return out


def _rounded(targets) -> str:
    """The fingerprint with every float to 10 significant digits: the form a pin can hold on any CPU.
    The repr form (`_fingerprint`) moves in the last ulp between an arm64 Mac and CI's x86 (the CI run
    of 3b4c963 showed it), so it is exact only on the pin machine (`_check_pins`)."""
    g = lambda x: "None" if x is None else format(float(x), ".10g")      # noqa: E731
    return "\n".join("|".join([t.instrument, t.side, t.kind, g(t.qty), g(t.weight), t.reason,
                                str(t.combo_id), repr(sorted(t.meta.items()))]) for t in targets)


PIN_MACHINE = "arm64"
# Exact on every machine: orders, plan_sha, plan targets, counts, exits, status, the rounded target
# fingerprints. Exact on the pin machine only, where floats are printed in full: the repr target
# fingerprints, plan.json and the run records (they carry gross, NAV and cap figures to 17 digits).
FLOAT_KEYS = frozenset({"plan_json", "run_record"})


class PinMachineDrift(UserWarning):
    """A full-precision pin moved off the pin machine; every stable entry still matched."""


def _check_pins(what: str, got: dict, pinned: dict, float_keys) -> None:
    """test_combine_noop's rule: everything on the pin machine; elsewhere the stable entries exactly,
    and a moved full-precision entry is a warning naming it, never silent."""
    assert set(got) == set(pinned), (what, sorted(set(got) ^ set(pinned)))
    if platform.machine() == PIN_MACHINE:
        assert got == pinned, what
        return
    flat = lambda d: {(k, kk): vv for k, v in d.items() for kk, vv in (v.items() if isinstance(v, dict)  # noqa: E731
                                                                       else [("", v)])}
    g, p = flat(got), flat(pinned)
    assert set(g) == set(p), what
    moved = sorted(k for k in p if k[0] in float_keys or k[1] in float_keys if g[k] != p[k])
    assert {k: g[k] for k in p if not (k[0] in float_keys or k[1] in float_keys)} == \
        {k: v for k, v in p.items() if not (k[0] in float_keys or k[1] in float_keys)}, what
    if moved:
        warnings.warn(f"{what}: full-precision entries {moved} differ on {platform.machine()} from the "
                      f"{PIN_MACHINE} pin; every stable entry matches exactly", PinMachineDrift)


def _weights(targets) -> dict:
    return {t.instrument: float(t.weight) for t in targets if t.weight}


# ---------------------------------------------------------------------------
# the pins (module docstring, HOW THE PINS WERE MADE)
# ---------------------------------------------------------------------------

def _absent_fingerprints(root: Path, spec: dict) -> dict:
    """{date|book: {repr, rounded}: sha of each fingerprint} for PIN_DATES, flat and held."""
    dates = pd.bdate_range(end=pd.Timestamp(ASOF), periods=N_DAYS)
    cap = float(spec["capital_usd"])
    out = {}
    for i in PIN_DATES:
        day = dates[i]
        flat = _targets(spec, day)
        held_book = _half(flat, _closes(root, day), cap)
        held = _targets(spec, day, held_book)
        # A pin on a held book where the cap binds would flake: its last ulp depends on the
        # hash seed (the band's set union orders `_cap_gross`'s sum; test_combine_noop.py).
        assert not any("gmax=" in t.reason and "*x" in t.reason for t in held), day
        assert any("band hold" in t.reason for t in held) and any(t.weight for t in held), day
        for lab, tg in (("flat", flat), ("held", held)):
            out[f"{day.date()}|{lab}"] = {"repr": _sha(_fingerprint(tg)), "rounded": _sha(_rounded(tg))}
    return out


def _v4_spec_bytes() -> "bytes | None":
    """C4's spec at BASE_COMMIT: the live file while it is v4, else `git show`; None when
    neither gives v4's bytes."""
    raw = C4_SPEC.read_bytes()
    if _sha(raw) == V4_FILE_SHA:
        return raw
    r = subprocess.run(["git", "-C", str(rn.REPO), "show",
                        f"{BASE_COMMIT}:ops/specs/c4_families.frozen.json"], capture_output=True)
    if r.returncode == 0 and _sha(r.stdout) == V4_FILE_SHA:
        return r.stdout
    return None


def _session_hashes(root: Path, work: Path, spec: dict, mp) -> dict:
    """A C4 session in DRY on the generated panel, through default_deps from C4's book json
    (test_c4_book's `_c4_session`, with the spec passed in): the evening decide, then the
    15:52 send. Paths under `work` are normalised out of the hashed bytes."""
    from quantt.broker import alpaca
    from quantt.session.tests.test_c4_book import EVE, SEND, SESSION, _C4Client, _c4
    state = work / "quantt_state" / "c4"
    state.mkdir(parents=True)
    norm = lambda b: (b.replace(str(work).encode(), b"<WORK>")             # noqa: E731
                      .replace(str(rn.REPO).encode(), b"<REPO>"))
    out = {}
    for label, now in (("decide", EVE), ("send", SEND)):
        c = _C4Client(state, now)
        mp.setattr(alpaca.AlpacaClient, "from_environment",
                   classmethod(lambda cls, name, **kw: c))
        deps = rn.default_deps(_c4(), spec, {"QUANTT_ENV_FILE": "unused"})
        deps.env = {"QUANTT_STATE_DIR": str(state), "DRY_RUN": "1"}
        deps.refresh = lambda a, t: rn.RefreshResult(exit=0, tail="fixture")
        deps.halts = lambda: []
        deps.utcnow = lambda now=now: now.astimezone(dt.timezone.utc)
        deps.out = type("Quiet", (), {"write": lambda self, s: None, "flush": lambda self: None})()
        code = rn.run_session(_c4(), spec, deps)
        day = state / SESSION
        runs = sorted((day / "runs").glob("*.json"))
        out[label] = {"exit": code, "run_record": _sha(norm(runs[-1].read_bytes())),
                      "submits": len(c.submits())}
        if label == "decide":
            raw = (day / "plan.json").read_bytes()
            plan = json.loads(raw)
            out[label].update(plan_json=_sha(norm(raw)), plan_sha=plan["plan_sha"],
                              status=plan["status"], n_orders=len(plan["orders"]),
                              orders=_sha(json.dumps(plan["orders"], sort_keys=True)),
                              targets=_sha(json.dumps(plan["targets"], sort_keys=True)))
    return out


def print_pins():
    """Print every pin (module docstring). Uses only what f7f7be5 has."""
    import tempfile
    with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
        root, panel, _ = _panel(Path(d), mp)
        spec = _absent_spec()
        print("V4_FROZEN_SHA =", repr(_sha(_canon(spec["frozen"]))))
        print("PANEL_SHA =", repr(panel))
        print("TARGET_PINS =", json.dumps(_absent_fingerprints(root, spec), indent=1, sort_keys=True))
    with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
        root, _, _ = _panel(Path(d), mp)
        raw = _v4_spec_bytes()
        print("SESSION_PINS =", json.dumps(_session_hashes(root, Path(d), json.loads(raw), mp),
                                           indent=1, sort_keys=True))


# PINNED 2026-11-03 (module docstring): TARGET_PINS by f7f7be5's code and again by 4485a96's (origin/main
# after the merge), identical; SESSION_PINS by 4485a96's, whose runner (#40, the C4 arming gate) writes a
# different plan.json and run record from f7f7be5's. Each unseeded and under PYTHONHASHSEED 1 and 2,
# identical every time, and identical on this tree. Arm64 Mac, Python 3.13.5, pandas 2.3.3, numpy 2.3.4.
PANEL_SHA = "40f63cf6abe235957e2ab157693f44636619a6bdf803c94c3c6503758e53c80c"
TARGET_PINS = {
    "2026-08-14|flat": {"repr": "44bcd85d2a1463dfa760e18da25c4133060daaba8d16b22532522ade7a279a3e", "rounded": "c0a53875acacab6ba3f9e92891a518bc5557088e22b541a8eb40d6ea16589020"},
    "2026-08-14|held": {"repr": "683adac58b4ebe11cc7747324412f378b081180ee68f69211243a71e5d585585", "rounded": "3d8357b7b40543cb5d4e692073965f22170ddd5ce987a52a0c2ffe9eaefa0882"},
    "2026-09-24|flat": {"repr": "e1c28269ac8840a61295a32c75d77b0ee7a4be89387cf50bd3d23047db5399b1", "rounded": "d2203cf257cbe126810711bdcf848731ce9aa48e9870d1ab87336a37aa00e48f"},
    "2026-09-24|held": {"repr": "b6ab80b1e1e49561cffd95a26fb7e622bfb97c9515f102b870bdbe20f100b2a1", "rounded": "f7ddaf06e7dc796dc52bd653bd14871e81fa04b18110738632c67f878a2969c9"},
    "2026-09-25|flat": {"repr": "475d91fa100eed698b9c7eeec2a3b5c7dbbe334357260b466d266b593b710207", "rounded": "a5170a98a91ad3ac623dd5da50a14c14e8b21cfb53b8e758606da078dafe952f"},
    "2026-09-25|held": {"repr": "638c99c7752010aa9540606794906a1e450d2c8c63fb4a651e13ddd8e97001a0", "rounded": "b910637456e2ad105b368eef407e59bd8e3c889ae0953f337c1eaad2f7c81df4"},
}
SESSION_PINS = {
    "decide": {
        "exit": 6,
        "n_orders": 60,
        "orders": "dc62cc3047434e6e004edc0ada3c0c9f354397837dcff43cde1ec9ed1d0c8d14",
        "plan_json": "488434c6d3e3958cf83e1734296192f102d2159fedce966f6b4db903650a18bb",
        "plan_sha": "9a45e9805d3ac937009c9dc5cb923eb5ccf62fdceb6b8e2ff4874606687848d4",
        "run_record": "10638d0fa02f89794f848acdd16a57206e16c77b437a8f0a21bb1ae3dd52626f",
        "status": "decided",
        "submits": 0,
        "targets": "f6ab2ad2e9ca4253b88085c260e6e90d128649dc7e7b4c6944a786208d1feaf2",
    },
    "send": {
        "exit": 10,
        "run_record": "bf94169f1cefdb24ee6ad54cb9c767a154f3ac1dcf5fc4e9d91bb7cb211e9b0d",
        "submits": 0,
    },
}


# ---------------------------------------------------------------------------
# 1-2. the no-op
# ---------------------------------------------------------------------------

def test_key_absent_targets_are_f7f7be5s(tmp_path, monkeypatch):
    root, panel, _ = _panel(tmp_path, monkeypatch)
    assert panel == PANEL_SHA, "the generator drifted, not the code: re-derive the pins"
    spec = _absent_spec()
    assert _sha(_canon(spec["frozen"])) == V4_FROZEN_SHA, \
        "C4's live spec minus level_signal is not v4's frozen block: something else moved"
    _check_pins("C4 v4 targets, key absent", _absent_fingerprints(root, spec), TARGET_PINS, {"repr"})


def test_key_absent_session_is_f7f7be5s(tmp_path, monkeypatch):
    raw = _v4_spec_bytes()
    if raw is None:
        why = (f"C4 LEVEL NO-OP SESSION PIN NOT APPLIED: neither {C4_SPEC} nor git show "
               f"{BASE_COMMIT} gave c4_families.v4's bytes (sha {V4_FILE_SHA[:12]}...); the "
               f"target pin still runs")
        warnings.warn(why, LevelPinNotApplicable)
        pytest.skip(why)
    root, _, _ = _panel(tmp_path, monkeypatch)
    got = _session_hashes(root, tmp_path, json.loads(raw), monkeypatch)
    _check_pins("C4 v4 session, key absent", got, SESSION_PINS, FLOAT_KEYS)
    assert got["decide"]["exit"] == rn.EXIT_PLANNED and got["decide"]["n_orders"] > 0
    assert got["send"]["exit"] == rn.EXIT_DRY and got["send"]["submits"] == 0


# ---------------------------------------------------------------------------
# 3-4. what the key does: the blend is §1.2, and a lone family contributes zero
# ---------------------------------------------------------------------------

def _probe(sleeve, day, ms):
    """(targets, the frame's locals at the `min_abs_weight` read): the unit target `w` after
    the vol scalar, the eligible `row`, the masked `disc`, `px` and the signal date `last`.
    The same point C4's fidelity probe reads (scripts/cef/c4_paper_benchmark.py `Probe`)."""
    seen = {}
    orig = sleeve._req
    code = CEFDiscountSleeve.target_positions.__code__

    def req(key):
        v = orig(key)
        if key == "min_abs_weight":
            f = sys._getframe(1)
            assert f.f_code is code and not seen, "min_abs_weight read elsewhere or twice"
            loc = f.f_locals
            seen.update(w=loc["w"].copy(), row=dict(loc["row"]), disc=loc["disc"],
                        px=loc["px"], last=loc["last"])
        return v

    sleeve._req = req
    out = sleeve.target_positions(pd.Timestamp(day), ms)
    assert seen, "the decide never reached the min_abs_weight read"
    return out, seen


def _reference(seen, family_of, risk_share, vol_target, gross_leverage):
    """§1.2, re-derived with numpy and loops from the sleeve's own inputs (its eligible names,
    their date-t z and masked discount, and the price panel), sharing no code with the sleeve."""
    names = list(seen["row"])
    z = np.array([seen["row"][t] for t in names])
    wz = -(z - z.mean())
    wz = wz / np.abs(wz).sum()
    d = np.array([float(seen["disc"].loc[seen["last"], t]) for t in names])
    wl = np.zeros(len(names))
    by = {}
    for i, t in enumerate(names):
        by.setdefault(family_of[t], []).append(i)
    for idx in by.values():
        if len(idx) >= 2:
            m = sum(d[i] for i in idx) / len(idx)
            for i in idx:
                wl[i] = -(d[i] - m)
    wl = wl / np.abs(wl).sum()
    px = seen["px"]
    assert px.index[-1] == seen["last"]
    r = px[names].pct_change(fill_method=None)
    R = r.where(r.abs() < 0.5).fillna(0.0).to_numpy()[-63:]

    def vol(w):
        return float((R @ w).std(ddof=1) * math.sqrt(252))

    sz, sl = vol(wz), vol(wl)
    mix = risk_share * wz / sz + (1.0 - risk_share) * wl / sl
    mix = mix / np.abs(mix).sum()
    scal = min(max(vol_target / vol(mix), 0.2), 2.5)
    return (pd.Series(mix * scal * gross_leverage, index=names),
            {"wz": pd.Series(wz, index=names), "wl": pd.Series(wl, index=names), "sz": sz, "sl": sl})


def _blend_case(tmp_path, monkeypatch, family_of=None, risk_share=0.5, day=None):
    _panel(tmp_path, monkeypatch)
    fam = _families() if family_of is None else family_of
    spec = _with_level(_absent_spec(), risk_share, fam)
    f = spec["frozen"]
    day = pd.Timestamp(ASOF) if day is None else day
    sl = registry.build_sleeve(spec, float(spec["capital_usd"]))
    out, seen = _probe(sl, day, _ms(day))
    want, parts = _reference(seen, fam, risk_share, float(f["vol_target_annual"]),
                             float(f["gross_leverage"]))
    return spec, out, seen, want, parts


def test_the_blend_is_the_preregistered_construction(tmp_path, monkeypatch):
    """§1.2 steps 1-4 on C4's spec (masks on, ADV floor, band, cap, multiplier). The level is
    built on exactly the z's eligible names: the masked and illiquid funds are in neither.
    Fails on f7f7be5: its `w` is the z book alone, which differs from the blend."""
    spec, out, seen, want, parts = _blend_case(tmp_path, monkeypatch)
    w = seen["w"]
    for gone in (ILLIQUID, M1_TODAY, M2_TODAY):
        assert gone not in seen["row"], gone          # the z's eligibility, applied to the level
    assert list(w.index) == list(want.index)
    assert float((w - want).abs().max()) < 1e-12
    # not vacuous: the level moved the book, and every target says the blend made it
    z_only = parts["wz"] * float(np.clip(spec["frozen"]["vol_target_annual"] / parts["sz"], 0.2, 2.5))
    assert float((w - z_only).abs().max()) > 1e-3
    assert all(" level z_share=0.5000 s_z=" in t.reason for t in out if t.weight)
    # dollar-neutral within every family, before the blend mixes them
    fam = _families()
    for f in set(fam[t] for t in parts["wl"].index):
        assert abs(sum(v for t, v in parts["wl"].items() if fam[t] == f)) < 1e-15, f


def test_a_family_with_one_eligible_name_contributes_zero(tmp_path, monkeypatch):
    """A one-name family has no peer to be rich or cheap against. Two cases: ADX alone in its
    family, and a pair (ASG, ILLIQUID) whose other member the ADV floor drops, so the family
    mean is taken over ELIGIBLE names only. Either way the name's blended weight is its z part
    alone. Fails on f7f7be5 (no level book: the sleeve's w is not the reference)."""
    fam = dict(_families(), ADX="solo", ASG="pair", **{ILLIQUID: "pair"})
    _, out, seen, want, parts = _blend_case(tmp_path, monkeypatch, family_of=fam)
    assert ILLIQUID not in seen["row"] and {"ADX", "ASG"} <= set(seen["row"])
    assert parts["wl"]["ADX"] == 0.0 and parts["wl"]["ASG"] == 0.0
    assert float((seen["w"] - want).abs().max()) < 1e-12
    # and the sleeve's own w_L says so, exactly
    from src.deploy.sleeves.cef_discount import _level_weights
    names = list(seen["row"])
    wl = _level_weights(seen["disc"].loc[seen["last"], names], fam)
    assert wl["ADX"] == 0.0 and wl["ASG"] == 0.0
    assert float((wl - parts["wl"]).abs().max()) < 1e-15


def test_level_weights_by_hand():
    """`_level_weights` on a hand-made row: within-family demeaning, unit gross, rich short and
    cheap long, a singleton exactly zero; an all-singleton row has no level book and raises."""
    from src.deploy.sleeves.cef_discount import _level_weights
    d = pd.Series({"A": -10.0, "B": -4.0, "C": 2.0, "D": -6.0, "E": -1.0})
    fam = {"A": "x", "B": "x", "C": "y", "D": "y", "E": "z"}
    w = _level_weights(d, fam)
    # family x mean -7: A -3 -> +3 (cheap, long), B +3 -> -3; y mean -2: C +4 -> -4, D -4 -> +4
    assert w.to_dict() == {"A": 3 / 14, "B": -3 / 14, "C": -4 / 14, "D": 4 / 14, "E": 0.0}
    assert list(w.index) == list(d.index)
    with pytest.raises(ValueError, match="no gross"):
        _level_weights(d[["A", "C", "E"]], fam)
    with pytest.raises(ValueError, match="non-finite discount"):
        _level_weights(pd.Series({"A": np.nan, "B": -4.0}), fam)


# ---------------------------------------------------------------------------
# 5. a ticker missing from family_of raises, naming it
# ---------------------------------------------------------------------------

def test_a_ticker_missing_from_family_of_raises_naming_it():
    """At load (the registry), at construction (the sleeve, built without the registry), and
    in `_level_weights` for an eligible name. Fails on f7f7be5, which ignores the key."""
    fam = _families()
    del fam["ETV"]
    spec = _with_level(_absent_spec(), family_of=fam)
    with pytest.raises(ValueError, match=r"no family for \['ETV'\]"):
        registry.validate_spec(spec)
    with pytest.raises(ValueError, match=r"no family for \['ETV'\]"):
        CEFDiscountSleeve(spec, float(spec["capital_usd"]))
    from src.deploy.sleeves.cef_discount import _level_weights
    with pytest.raises(ValueError, match=r"no family for eligible ticker\(s\) \['ETV'\]"):
        _level_weights(pd.Series({"ETW": -5.0, "ETV": -3.0}), {"ETW": "equity_covered_call"})


# ---------------------------------------------------------------------------
# 6. the blend reads nothing after t
# ---------------------------------------------------------------------------

def test_the_blend_reads_nothing_after_t(tmp_path, monkeypatch):
    """Every price, NAV and volume row after t rewritten leaves t's blended targets
    byte-identical, on a flat and a held book; and the targets are the blend's (not
    vacuous: they differ from the key absent). Fails on f7f7be5 (no blend)."""
    root, _, dates = _panel(tmp_path, monkeypatch)
    t = dates[-31]
    spec = _with_level(_absent_spec())
    flat = _targets(spec, t)
    held_book = _half(flat, _closes(root, t), float(spec["capital_usd"]))
    before = (_fingerprint(flat), _fingerprint(_targets(spec, t, held_book)))
    assert _fingerprint(_targets(_absent_spec(), t)) != before[0]
    assert all(" level z_share=" in x.reason for x in flat if x.weight)
    d = root / "data" / "cef_c4"
    P, N = pd.read_parquet(d / "cef_prices.parquet"), pd.read_parquet(d / "cef_nav.parquet")
    after_p, after_n = pd.to_datetime(P["date"]) > t, pd.to_datetime(N["date"]) > t
    assert after_p.sum() > 0 and after_n.sum() > 0
    k = np.arange(len(P))
    P.loc[after_p, "close"] = P.loc[after_p, "close"] * (1.0 + 0.3 * np.sin(k[after_p]))
    P.loc[after_p, "volume"] = 0
    N.loc[after_n, "nav"] = N.loc[after_n, "nav"] * 1.25
    P.to_parquet(d / "cef_prices.parquet")
    N.to_parquet(d / "cef_nav.parquet")
    assert (_fingerprint(_targets(spec, t)), _fingerprint(_targets(spec, t, held_book))) == before


def test_the_alignment_check_refuses_returns_past_the_signal_date(tmp_path, monkeypatch):
    """The registry requires a band with the key, so the signal date is the last paired session.
    Forced onto the rebalance_days calendar (a test patch the registry cannot be talked into),
    the signal date falls a session before the panel's end on alternate days, and the blend
    must refuse rather than read returns past it. Fails on f7f7be5 (nothing to refuse)."""
    _, _, dates = _panel(tmp_path, monkeypatch)
    spec = _with_level(_absent_spec())
    monkeypatch.setattr(CEFDiscountSleeve, "_band_width", property(lambda self: None))
    raised = 0
    for day in (dates[-1], dates[-2]):
        try:
            _targets(spec, day)
        except AssertionError as exc:
            assert "returns through the signal date only" in str(exc)
            raised += 1
    assert raised == 1


# ---------------------------------------------------------------------------
# 7. the risk_share -> 1 limit is the z book
# ---------------------------------------------------------------------------

def test_the_risk_share_one_limit_is_the_z_book(tmp_path, monkeypatch):
    """risk_share 1.0 puts every unit of risk on z: w_L's part is 0 x w_L / s_L, and the blend
    renormalises w_z / s_z back to w_z. The key refuses 1.0 (the z book is the key ABSENT), so
    the limit is reached by patching the parsed value. Equal to the key absent to 1e-12 in
    every weight, name for name and side for side; the reasons differ only by the level tag
    (the vol scalar's 2-dp print aside, which agrees here). Fails on f7f7be5, which has no
    `_level_signal` to patch."""
    _panel(tmp_path, monkeypatch)
    absent = _targets(_absent_spec(), pd.Timestamp(ASOF))
    fam = _families()
    monkeypatch.setattr(CEFDiscountSleeve, "_level_signal",
                        property(lambda self: {"risk_share": 1.0, "family_of": fam}))
    limit = _targets(_absent_spec(), pd.Timestamp(ASOF))
    assert [(t.instrument, t.side) for t in limit] == [(t.instrument, t.side) for t in absent]
    wa, wl = _weights(absent), _weights(limit)
    assert set(wa) == set(wl) and max(abs(wa[k] - wl[k]) for k in wa) < 1e-12
    tagged = [t.reason for t in limit if t.weight]
    assert tagged and all(" level z_share=1.0000" in r for r in tagged)
    tag = re.compile(r" level z_share=1\.0000 s_z=\d+\.\d{4} s_L=\d+\.\d{4}")
    assert [tag.sub("", t.reason, count=1) for t in limit] == [t.reason for t in absent]


# ---------------------------------------------------------------------------
# 8. the cap still binds
# ---------------------------------------------------------------------------

def test_the_cap_binds_at_max_gross_stress_over_m(tmp_path, monkeypatch):
    """The blend has more gross per unit of risk than z alone (§3.3), so the cap binds more
    often; it must still bind at max_gross_stress / m in unit weights, so that m x the emitted
    unit book is at most max_gross_stress x NAV. Both numbers are read from C4's spec. On a
    flat (opening) book and on a held book. Fails on f7f7be5 (no blend: no level tag)."""
    root, _, _ = _panel(tmp_path, monkeypatch)
    spec = _with_level(_absent_spec())
    f = spec["frozen"]
    cap, m = float(f["max_gross_stress"]), float(f["sizing_multiplier"])
    sl = registry.build_sleeve(spec, float(spec["capital_usd"]))
    flat, seen = _probe(sl, ASOF, _ms(ASOF))
    assert float(seen["w"].abs().sum()) * m > cap, "precondition: the cap must bind"
    w = _weights(flat)
    assert sum(abs(v) for v in w.values()) <= cap + 1e-12
    assert all(f"gmax={cap:.4f}*x" in t.reason and f"smult={m:.4f}" in t.reason
               and " level z_share=" in t.reason for t in flat if t.weight)
    held = _targets(spec, ASOF, _half(flat, _closes(root, ASOF), float(spec["capital_usd"])))
    cap_usd = cap * float(spec["capital_usd"])
    closes = _closes(root, ASOF)
    gross_usd = sum(abs(float(t.weight)) * float(spec["capital_usd"]) if t.weight else
                    abs(float(t.qty or 0.0)) * closes[t.instrument] for t in held)
    assert gross_usd <= cap_usd * (1 + 1e-9)


# ---------------------------------------------------------------------------
# 9. equal risk
# ---------------------------------------------------------------------------

def test_equal_risk_contributions_on_known_vols():
    """§1.3 test 3. Returns built from two independent unit series with known scales: the z
    book's P&L has 3x the level book's vol. At risk_share 0.5 the two parts of the blend
    (before the one renormalisation, which scales both alike) have equal standalone vol, and
    so equal Euler contributions to the blend's vol, to 1e-12; at 0.3 the vols are 0.3 : 0.7.
    The vols the blend divides by are the realised ones. Fails on f7f7be5 (no blend)."""
    from src.deploy.sleeves.cef_discount import _blend_unit_book, _book_vol
    idx = pd.bdate_range("2026-01-02", periods=80)
    g = _lcg(54)
    a = np.array([((next(g) % 20001) - 10000) / 10000.0 for _ in idx])
    b = np.array([((next(g) % 20001) - 10000) / 10000.0 for _ in idx])
    # names A,B carry factor a (the z book's), C,D factor b (the level book's), at 3:1 scale
    ret = pd.DataFrame({"A": 0.03 * a, "B": -0.03 * a, "C": 0.01 * b, "D": -0.01 * b}, index=idx)
    w_z = pd.Series({"A": 0.5, "B": -0.5, "C": 0.0, "D": 0.0})
    w_L = pd.Series({"A": 0.0, "B": 0.0, "C": 0.5, "D": -0.5})
    R = ret.to_numpy()[-63:]
    sd = lambda x: float(x.std(ddof=1) * math.sqrt(252))     # noqa: E731
    assert abs(sd(R @ w_z.to_numpy()) / sd(R @ w_L.to_numpy()) - 3.0 * sd(a[-63:]) / sd(b[-63:])) < 1e-12
    for rs in (0.5, 0.3):
        mix, vols = _blend_unit_book(w_z, w_L, ret, rs)
        assert abs(vols["s_z"] - sd(R @ w_z.to_numpy())) < 1e-15
        assert abs(vols["s_L"] - sd(R @ w_L.to_numpy())) < 1e-15
        G = float((rs * w_z / vols["s_z"] + (1 - rs) * w_L / vols["s_L"]).abs().sum())
        pz, pl = rs * w_z / vols["s_z"] / G, (1 - rs) * w_L / vols["s_L"] / G
        assert float((pz + pl - mix).abs().max()) < 1e-15 and abs(float(mix.abs().sum()) - 1) < 1e-15
        vz, vl = _book_vol(ret, pz), _book_vol(ret, pl)
        assert abs(vz / vl - rs / (1 - rs)) < 1e-12
        hz, hl = R @ pz.to_numpy(), R @ pl.to_numpy()
        h = hz + hl
        rc_z = float(np.cov(hz, h, ddof=1)[0, 1]) / float(h.std(ddof=1))
        rc_l = float(np.cov(hl, h, ddof=1)[0, 1]) / float(h.std(ddof=1))
        assert abs((rc_z + rc_l) - float(h.std(ddof=1))) < 1e-12
        if rs == 0.5:
            assert abs(vz - vl) < 1e-12 and abs(rc_z - rc_l) < 1e-12
            assert abs(vols["s_mix"] - _book_vol(ret, mix)) == 0.0


# ---------------------------------------------------------------------------
# 9b. the combiner refuses the key (§1.3 test 7)
# ---------------------------------------------------------------------------

def test_a_combined_book_refuses_the_level_signal(tmp_path):
    """§1.3 test 7: a budgeted sleeve whose spec carries level_signal is refused by the combiner, as
    one carrying sizing_multiplier is. The blend was measured only as one account's book. The spec
    here drops sizing_multiplier, so the refusal is the key's own; with the key removed as well, the
    same book loads (the refusal is not the book's). Fails on f7f7be5, which loads it."""
    from quantt.session import combine as cmb
    base = _absent_spec()
    del base["frozen"]["sizing_multiplier"]
    del base["frozen"]["_sizing_multiplier_note"]
    bj = tmp_path / "book.json"
    bj.write_text(json.dumps({"book_id": "t", "sleeves": [
        {"name": "c4", "enabled": True, "spec_path": "s.json", "risk_budget": 1.0}]}))
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(_with_level(base)))
    with pytest.raises(cmb.CombineError, match="level_signal"):
        cmb.load_sleeves(bj, sp, tmp_path, lambda spec: (lambda *a, **k: []))
    sp.write_text(json.dumps(base))
    got = cmb.load_sleeves(bj, sp, tmp_path, lambda spec: (lambda *a, **k: []))
    assert got is not None and len(got) == 1


# ---------------------------------------------------------------------------
# 10. the registry refuses
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [0, 0.0, 1, 1.0, -0.1, 1.5, float("nan"), float("inf"), True,
                                 "0.5", None, [0.5]])
def test_the_registry_refuses_a_bad_risk_share(bad):
    with pytest.raises(ValueError, match="level_signal.risk_share"):
        registry.validate_spec(_with_level(_absent_spec(), risk_share=bad))


@pytest.mark.parametrize("value", [None, [], "on", 0.5,
                                   {"risk_share": 0.5},
                                   {"family_of": {"ADX": "x"}},
                                   {"risk_share": 0.5, "family_of": {}, "extra": 1}])
def test_the_registry_refuses_a_malformed_object(value):
    s = _absent_spec()
    s["frozen"]["level_signal"] = value
    with pytest.raises(ValueError, match="level_signal must be an object with exactly"):
        registry.validate_spec(s)


@pytest.mark.parametrize("fix", ["empty", "not_a_dict", "blank_family", "number_family", "stray"])
def test_the_registry_refuses_a_bad_family_map(fix):
    fam = _families()
    if fix == "empty":
        fam = {}
    elif fix == "not_a_dict":
        fam = sorted(fam.items())
    elif fix == "blank_family":
        fam["ADX"] = " "
    elif fix == "number_family":
        fam["ADX"] = 3
    elif fix == "stray":
        fam["ZZZZ"] = "preferred"
    with pytest.raises(ValueError, match="level_signal.family_of"):
        registry.validate_spec(_with_level(_absent_spec(), family_of=fam))


def test_the_key_needs_a_band():
    s = _with_level(_absent_spec())
    del s["frozen"]["band_width"]
    with pytest.raises(ValueError, match="band_width is not"):
        registry.validate_spec(s)
    s["frozen"]["band_width"] = None
    with pytest.raises(ValueError, match="band_width is not"):
        registry.validate_spec(s)


@pytest.mark.parametrize("key", ["level_signals", "level_signl", "_level_signal", "levelsignal",
                                 "Level-Signal", "_level_signals_note"])
def test_the_registry_refuses_a_near_miss_spelling(key):
    s = _absent_spec()
    s["frozen"][key] = {"risk_share": 0.5, "family_of": _families()}
    with pytest.raises(ValueError, match="misspelling of 'level_signal'"):
        registry.validate_spec(s)


def test_a_well_formed_key_and_its_note_validate_and_parse():
    """The positive case, so the refusals above are not a refusal of everything: risk_share
    is the share of risk on Z, the map is copied, and the note is not a near miss."""
    s = _with_level(_absent_spec(), risk_share=0.5)
    s["frozen"]["_level_signal_note"] = "the sibling note"
    registry.validate_spec(s)
    got = registry.cef_level_signal(s["frozen"])
    assert got == {"risk_share": 0.5, "family_of": _families()}
    assert got["family_of"] is not s["frozen"]["level_signal"]["family_of"]
    assert registry.cef_level_signal(_absent_spec()["frozen"]) is None
    # every key both live specs carry today is clear of the near-miss rule
    for path in (C4_SPEC, rn.REPO / "ops" / "specs" / "cef_discount.frozen.json"):
        registry.validate_spec(json.loads(path.read_text()))


# ---------------------------------------------------------------------------
# 11. the activation (this test pins the spec, not the code)
# ---------------------------------------------------------------------------

def test_the_c4_spec_carries_trial_54s_level_signal_with_its_note():
    """The activation, /spec-change steps 4-5, after CEF trial 54 passed (holdout decisive; K3 overridden
    post-data by the team lead): C4's spec is c4_families.v5.20261103, superseding v4, with `level_signal`
    at risk_share 0.5 (the share of risk on z, PREREG_C4_LEVEL §3.1) and family_of exactly the frozen
    CSV's `family` column (74 rows, in the universe's order), and its sibling note. The note records the
    result as it is (K3 overridden, not passed), the §3.3 figures re-measured on the sleeve's construction
    beside the design run's, the turnover correction, L1's reference and the stops' sources. Deleting the
    key and its note leaves v4's frozen block (test 1 holds that too). FAILS on the code commits 3b4c963
    and ec3b01a (key absent) and on f7f7be5, by design: it pins the activation. The REVERT is the note's."""
    s = _live_spec()
    f = s["frozen"]
    assert s["spec_id"] == "c4_families.v5.20261103"
    assert s["_supersedes"] == "c4_families.v4.20261102"
    got = registry.cef_level_signal(f)
    assert got["risk_share"] == 0.5
    assert got["family_of"] == _families() and len(got["family_of"]) == 74
    assert list(got["family_of"]) == list(f["universe"])
    note = f["_level_signal_note"]
    for must in ("CEF TRIAL 54", "PASSED", "OVERRIDDEN POST-DATA", "not a pass of K3", "INCONCLUSIVE",
                 "907 of 907", "UNITS", "FRACTION OF EX-ANTE RISK placed on the Z book", "DERIVED",
                 "1.071 : 1.011", "0.514", "PLATEAU", "NOT CHOSEN", "CONSEQUENCE",
                 "RE-MEASURED ON THE SLEEVE'S CONSTRUCTION [V]", "activation_measures_2026-11-03.txt",
                 "CORRECTION", "RISES", "STOPS", "L1", "stops.py --c4-exact", "READ BY", "combine.py",
                 "REVERT", "spec-c4_families.v4.20261102"):
        assert must in note, must
    # the note's re-measured figures are the measures file's, not retyped
    m = json.loads((rn.REPO / "results" / "cef" / "prereg_c4_level" /
                    "activation_measures_2026-11-03.json").read_text())
    b, z = m["section_3_3"]["blend_spec_book"], m["section_3_3"]["z_only_spec_book"]
    for x in (f"target gross {b['target_gross']:.3f}", f"held at the cap on {b['p_at_cap']:.1%}",
              f"turnover {b['turn_per_yr']:.1f} turns a year", f"z {z['turn_per_yr']:.1f})",
              f"{m['l1']['price_only']['p5_120_sb21'] * 100:+.2f}% over 120 sessions"):
        assert x in note, x
    assert m["spec_sha256"] == _sha(C4_SPEC.read_bytes()), "the measures were not made on this spec file"
    assert _sha(_canon(_absent_spec()["frozen"])) == V4_FROZEN_SHA
    assert s["_spec_id_note"].startswith("v5.20261103 = v4.20261102 plus CEF trial 54's")
    registry.validate_spec(s)
    registry.build_sleeve(s, float(s["capital_usd"]))
