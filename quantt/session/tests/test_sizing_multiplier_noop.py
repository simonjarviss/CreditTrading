"""`sizing_multiplier` (CEF trial 53) ABSENT is 35b429f, byte for byte, through the whole session.

WHAT IS PROVED. The key (src/deploy/sleeves/cef_discount.py, module docstring) changes the sleeve
only when it is set. With it ABSENT, and with it present at exactly 1.0, the session is
byte-identical to 35b429f's. 35b429f is origin/main when the pre-registration was approved:
release-era code with the missing-NAV hold switched on (cee16ad).

The comparison covers exit, plan.json, plan_sha, orders, targets, refusals, the run record,
nav_gate.csv, send.json and what reached the broker. It runs five scenarios, each with the book
json's `data.missing_nav` ABSENT and set to "hold":
- a complete day: the evening decide, then the 15:52 send;
- a day with one as-of NAV missing: the evening decide, the 14:30 final check in late-market mode,
  and the final check in `cls` mode.

The scenarios and their hashing are test_missing_nav_hold.py's (`_session`, `_hashes`), with the
hold's key passed through. The tests:
  * `test_synthetic_*` NEVER SKIP: test_combine_noop's generated 13-fund panel and fixture spec.
  * `test_real_panel_*`: the real sleeve, on a copy of the real panels through 2026-09-25 (the
    `test_combine_noop` input pin), with **the core's spec as it was at 35b429f**, read from git
    (`git show 35b429f:...`). That spec has no key. Once the core's value is set in the live spec,
    this is still the key-absent spec, so the proof survives the activation. The test warns and
    skips when the copy or that spec is not what the pin was made on, or when git cannot show it.

HOW THE PINS WERE MADE.
1. `git worktree add --detach <scratch>/wt35 35b429f`, with the real `data/` symlinked in, read
   only.
2. This file copied into that tree, and `print_pins()` run there unseeded and under
   PYTHONHASHSEED 1.
3. Then run on this tree.

The results were identical every time. 35b429f's sleeve has no key, so its pins ARE the key-absent
book. To re-derive, do exactly that again. Never edit a hash by hand.

Hermetic: test_run's FakeClient for the broker, fixed clocks, the refresh a fixture, no CEFConnect
(a reader that raises), and netguard refuses any socket.
"""
import copy
import hashlib
import json
import subprocess
import warnings
from pathlib import Path

import pytest

from quantt.session import run as rn
from quantt.session.tests import test_missing_nav_hold as M
from quantt.session.tests.test_combine_noop import (
    PINNED_INPUT as COMBINE_PINNED_INPUT,
    SYN_SPEC,
    RealPanelPinNotApplicable,
    _frozen_copy,
    _real_panel_ready,
)

BASE_COMMIT = "35b429f"
KEYS = {"missing_nav_absent": None, "missing_nav_hold": M.HOLD}


def _base_spec_bytes() -> bytes | None:
    """The core's frozen spec as of BASE_COMMIT (no `sizing_multiplier`), or None."""
    r = subprocess.run(["git", "-C", str(rn.REPO), "show",
                        f"{BASE_COMMIT}:ops/specs/cef_discount.frozen.json"], capture_output=True)
    return r.stdout if r.returncode == 0 and r.stdout else None


def _with_one(spec: dict) -> dict:
    s = copy.deepcopy(spec)
    s["frozen"]["sizing_multiplier"] = 1.0
    return s


def _scenarios(work: Path, base: Path, mp, spec, missing: str, key) -> dict:
    """test_missing_nav_hold's `_absent_scenarios`, with the hold's key passed to every session."""
    out = {}
    M._scenario_panel(base, work / "complete" / "panel", mp, M.ASOF)
    cap = rn.spec_params(spec)["capital_usd"]
    held = M._held_book(spec, M.ASOF, cap)
    w = work / "complete"
    code, state, c, _ = M._session(w, spec, held, M.EVE, M.LATE_SCALE, refresh_exit=0, key=key)
    out["complete|decide"] = M._hashes(w, state, code, c)
    code, state, c, _ = M._session(w, spec, held, M.SEND, M.LATE_SCALE, refresh_exit=0,
                                   armed=True, key=key)
    out["complete|send"] = M._hashes(w, state, code, c, send=True)
    for label, now, ex, armed in (("eve", M.EVE, M.LATE_SCALE, False),
                                  ("final", M.FINAL, M.LATE_SCALE, False),
                                  ("final_cls", M.FINAL, M.CLS_SCALE, True)):
        w = work / f"missing_{label}"
        M._scenario_panel(base, w / "panel", mp, M.ASOF, nav=(missing,))
        code, state, c, _ = M._session(w, spec, held, now, ex, refresh_exit=4, armed=armed, key=key)
        out[f"missing|{label}"] = M._hashes(w, state, code, c)
    return out


def _synthetic(work: Path, mp, spec, key) -> dict:
    return _scenarios(work, M._synthetic_base(work, mp), mp, spec, M.SYN_MISSING, key)


def _real(work: Path, mp, key, at_one=False) -> dict | None:
    """None when git cannot show the base spec, or the real copy or that spec is not what the
    pin was made on."""
    raw = _base_spec_bytes()
    if raw is None:
        return None
    base = work / "base"
    base.mkdir(parents=True)
    spec = json.loads(raw)
    got = {"panel": _frozen_copy(base, mp, spec["frozen"]["universe"]),
           "spec": hashlib.sha256(raw).hexdigest()}
    if got != COMBINE_PINNED_INPUT:
        return None
    return _scenarios(work, base, mp, _with_one(spec) if at_one else spec, M.REAL_MISSING, key)


def print_pins():
    """Print both pins (module docstring, HOW THE PINS WERE MADE)."""
    import tempfile
    syn, real = {}, {}
    for label, key in KEYS.items():
        with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
            syn[label] = _synthetic(Path(d) / "syn", mp, SYN_SPEC, key)
        with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
            real[label] = _real(Path(d) / "real", mp, key)
    print("SYN_PINNED =", json.dumps(syn, indent=1, sort_keys=True))
    print("REAL_PINNED =", json.dumps(real, indent=1, sort_keys=True))


# PINNED 2026-11-01 on 35b429f (module docstring), on the laptop's dev panels (only rows
# through 2026-09-25 are read). Identical unseeded and under PYTHONHASHSEED 1, and on this tree.
SYN_PINNED = {
 "missing_nav_absent": {
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
 "missing_nav_hold": {
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
 }
}

REAL_PINNED = {
 "missing_nav_absent": {
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
   "targets": "978e2df32387f0be9e49a3a5966369bed1866e780b1ca8d79d562d11f2c37f56"
  },
  "complete|send": {
   "exit": 0,
   "run_record": "8003b25c902c0bc09863598ac0910fe44e0ca3ce245b912b05e8f07c28d37003",
   "send_json": "ac1adb88597ac75eb557fc634eae9f879b5196a07c03cdbbcfc05fa2a46d6a9b",
   "sent": "b30cc665d139dfebf931d9cac73299e66c22518a92a49e5c70d6a68e9532139d"
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
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
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
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
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
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
  }
 },
 "missing_nav_hold": {
  "complete|decide": {
   "exit": 6,
   "n_orders": 6,
   "nav_gate_csv": "18734cfdbe33cc779a2277bef135248fcafa1c90de9b2a0c203ae82a729af304",
   "orders": "f198dd92f1f473578190d104e61bd70d8bb2352ecb253bc12ccc6c9b23d75a2c",
   "plan_json": "da8602893fb148bae6227dcea166fde9de26bcdbb9f5c84cc0c831e41f2352f6",
   "plan_sha": "e69a46f6680840664ed3b44e21eb767cf4d9f641e0b3f9ee0fd07e45fa084e05",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "6b2f5e2fc5095a03715c90e674db43af24748d2a6d68a3d864a17c9d563bdc4b",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "decided",
   "targets": "978e2df32387f0be9e49a3a5966369bed1866e780b1ca8d79d562d11f2c37f56"
  },
  "complete|send": {
   "exit": 0,
   "run_record": "8003b25c902c0bc09863598ac0910fe44e0ca3ce245b912b05e8f07c28d37003",
   "send_json": "ac1adb88597ac75eb557fc634eae9f879b5196a07c03cdbbcfc05fa2a46d6a9b",
   "sent": "b30cc665d139dfebf931d9cac73299e66c22518a92a49e5c70d6a68e9532139d"
  },
  "missing|eve": {
   "exit": 11,
   "n_orders": 0,
   "nav_gate_csv": "18734cfdbe33cc779a2277bef135248fcafa1c90de9b2a0c203ae82a729af304",
   "orders": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "plan_json": "07ed83190bad6371138f20035962beabde965b77ad3704210271814e598f5337",
   "plan_sha": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "refusals": "45fb724cc5c4f4b809d81561866376313a6deee1633f27933aef93a6c4e09b03",
   "run_record": "55e1e0a78a4394c47e0f5f81cbede1488ea42402dd2a2e2a2b455b95a62caf96",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "refused",
   "targets": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
  },
  "missing|final": {
   "exit": 6,
   "n_orders": 5,
   "nav_gate_csv": "3e17b6fc3741ec740818874935a3a078f2b300f7ee49a86dd1204828f1597100",
   "orders": "8eed4bbdede1d23018a30be99b635b0de15d950e92dcb109a205e7f3b7df6369",
   "plan_json": "35d665a545dc2ce046281af36231e8ad4dbbac4418c0237aa2ec80dd8f884b03",
   "plan_sha": "335ff6880608490519e3c98bbf824d94ddc3bbaebd968290892c099fa1f32d44",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "26c1009974d0499ce407c9c9207f2fe04d0291280d82ea7eafc3fb6af7877548",
   "sent": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "status": "decided",
   "targets": "76f210ae5b86000c56d0cee23a8d046725f78b6795ec4c543d242ffd81561947"
  },
  "missing|final_cls": {
   "exit": 0,
   "n_orders": 5,
   "nav_gate_csv": "3e17b6fc3741ec740818874935a3a078f2b300f7ee49a86dd1204828f1597100",
   "orders": "0dc9a3fc8ed8347907e3c97b0dedbde02770b1eb34384b693e41cf45afcc11bd",
   "plan_json": "89ff6f5513af313530b83baf8b63633f8d916e1fb9e6d99c96e22590faabfedc",
   "plan_sha": "11a7e458821ae6b6f380183d33fde28c9dd4d406533cb4ec512c70506513ed14",
   "refusals": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
   "run_record": "9bd6b7e00277111f3889514b0034c1d580edb84374d6b60fa761ac253022b5c2",
   "sent": "64329bbbd615fe4d2ae0d658f443b9fde2e006213c9b0bfbd0f130572f7f0d93",
   "status": None,
   "targets": "76f210ae5b86000c56d0cee23a8d046725f78b6795ec4c543d242ffd81561947"
  }
 }
}


def _not_vacuous(got: dict, key):
    assert got["complete|decide"]["exit"] == rn.EXIT_PLANNED
    assert got["complete|decide"]["n_orders"] > 0
    assert got["complete|send"]["exit"] == rn.EXIT_SENT
    if key is None:          # without the hold a missing NAV refuses every slot
        assert {got[f"missing|{x}"]["exit"] for x in ("eve", "final", "final_cls")} == {rn.EXIT_REFUSED}
    else:                    # with it, the final check decides the other names
        assert got["missing|final"]["exit"] == rn.EXIT_PLANNED


@pytest.mark.parametrize("label", sorted(KEYS))
def test_synthetic_key_absent_is_35b429f(tmp_path, monkeypatch, label):
    got = _synthetic(tmp_path, monkeypatch, SYN_SPEC, KEYS[label])
    assert got == SYN_PINNED[label]
    _not_vacuous(got, KEYS[label])


@pytest.mark.parametrize("label", sorted(KEYS))
def test_synthetic_key_at_one_is_35b429f(tmp_path, monkeypatch, label):
    assert _synthetic(tmp_path, monkeypatch, _with_one(SYN_SPEC), KEYS[label]) == SYN_PINNED[label]


def _skip_real(why_input: str):
    why = (f"REAL-PANEL SIZING-MULTIPLIER NO-OP PIN NOT APPLIED: {why_input}. It was made on "
           f"panel/spec {COMBINE_PINNED_INPUT}, the spec read by `git show {BASE_COMMIT}:...`. "
           f"The synthetic pin still runs")
    warnings.warn(why, RealPanelPinNotApplicable)
    pytest.skip(why)


@pytest.mark.skipif(not _real_panel_ready(), reason="real CEF panels absent (data/ is "
                                                     "gitignored); the synthetic pin still runs")
@pytest.mark.parametrize("at_one", [False, True], ids=["absent", "at_one"])
@pytest.mark.parametrize("label", sorted(KEYS))
def test_real_panel_is_35b429f(tmp_path, monkeypatch, label, at_one):
    from src.deploy.sleeves import cef_discount as cefmod
    real = {f: f.read_bytes() for f in (cefmod.PX_PATH, cefmod.NAV_PATH)}
    got = _real(tmp_path, monkeypatch, KEYS[label], at_one=at_one)
    if got is None:
        _skip_real("git could not show the base spec, or this tree's panel copy differs")
    assert got == REAL_PINNED[label]
    _not_vacuous(got, KEYS[label])
    assert all(f.read_bytes() == b for f, b in real.items()), "a real panel changed"
