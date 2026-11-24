"""CEF trial 55 (te4) ABSENT is 0b1a2ef, byte for byte, through the whole session.

WHAT IS PROVED. `below_min_names = "trade_eligible"` (results/cef/
PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md, approved 2026-11-03, PAPER ONLY) changes the runner
only when the core spec sets it: the paper declaration and the endpoint check, K0 on the
drawdown record, the gate-7 flatten, plan.json's `thin_session` and `thin_stops`
(quantt/session/run.py, the `_thin_*` functions). With the key ABSENT, and with
`below_min_names: "flatten"` written out explicitly (the default, set IN MEMORY on a copy of
the spec, never in a file), the session is byte-identical to 0b1a2ef's: origin/main when this
pass began, which holds the owner's #40 and none of te4's runner code (§1.6 item 1, and the
owner's terms in the "Approval" section: "the core's no-op pins").

The comparison covers exit, plan.json, plan_sha, orders, targets, refusals, the run record,
nav_gate.csv, send.json and what reached the broker (test_missing_nav_hold.py's `_hashes`).
Scenarios, each with the book json's `data.missing_nav` ABSENT and "hold":
  * CORE: test_sizing_multiplier_noop.py's five (a complete day: the evening decide, then the
    15:52 send; a day with one as-of NAV missing: the evening decide, the 14:30 final check in
    late-market mode, and the final check in `cls` mode), on the synthetic panel (never skips)
    and on a frozen copy of the real panels through 2026-09-25 with the core's spec AS IT WAS
    AT 0b1a2ef (v9, x1.30), read from git, so the pin survives the activation commit.
  * THIN (synthetic, new): the same generated panel with the ADV of every name but the first
    5, 4 or 3 of THIN_ELIGIBLE pushed under the $3m floor over the last 80 sessions, so the
    sleeve finds exactly that many eligible names on the as-of date. Two books: FLAT (no
    position, one filled order in the history, so not an opening session: the re-entry after
    a flat day) and HELD (half the complete panel's day-one book). Three drawdown records,
    from `<state>/eod_equity.csv` against the fixture spec's 12% / 18% lines: OK, HALVE and
    absent (UNMEASURED). The late-market evening decide.
With the key absent the thin sessions are today's flatten, whatever the drawdown reads; with
it set (later commits) the same scenarios are what K0, the reduced build and the gate-7
flatten act on, so these pins are the "before" of every one of them.

These pass on the old code BY DESIGN, and must keep passing after every te4 commit.

HOW THE PINS WERE MADE (2026-11-03).
1. `git worktree add --detach <scratch>/pins 0b1a2ef2b308101b3512aec24dc49a22de98c888`, with
   the real `data/` symlinked in, read only.
2. This file copied into that tree and `print_pins()` run there, unseeded and under
   PYTHONHASHSEED 1: identical.
3. Then run on this tree: identical.
Each scenario is pinned as [exit, orders in the plan, plan status, digest], the digest being
sha256 of `_hashes`' dict as sorted JSON. A failure names the scenario; to see which output
moved, run print_pins() on both trees and diff. The core synthetic digests equal the digests of
test_sizing_multiplier_noop's SYN_PINNED (pinned on 35b429f), and the test checks that too.
Never edit a digest by hand; re-derive as above.

Hermetic: test_run's FakeClient for the broker, fixed clocks, the refresh a fixture, no
CEFConnect (a reader that raises), and netguard refuses any socket.
"""
import copy
import datetime as dt
import hashlib
import json
import subprocess
import warnings
from pathlib import Path

import pandas as pd
import pytest

from quantt.session import run as rn
from quantt.session.tests import test_missing_nav_hold as M
from quantt.session.tests import test_sizing_multiplier_noop as S
from quantt.session.tests.test_combine_noop import (
    N_DAYS,
    PINNED_INPUT as COMBINE_PINNED_INPUT,
    SYN_SPEC,
    RealPanelPinNotApplicable,
    _frozen_copy,
    _real_panel_ready,
)

BASE_COMMIT = "0b1a2ef2b308101b3512aec24dc49a22de98c888"
KEYS = {"missing_nav_absent": None, "missing_nav_hold": M.HOLD}
RULES = ("absent", "flatten")

# The thin panel: these names, in this order, are the eligible ones; every other name's volume
# is cut to THIN_VOLUME over the last THIN_SESSIONS rows, so its 63-session ADV (price x volume,
# about $10 x 50,000) is under the fixture spec's $3m floor on the as-of date. Chosen so the
# reduced build (key set) holds both sides: SYC and SYD short, the rest long, at 4 and 5.
THIN_ELIGIBLE = ("SYA", "SYB", "SYC", "SYD", "SYE")
THIN_COUNTS = (5, 4, 3)
THIN_VOLUME, THIN_SESSIONS = 50_000, 80
# The fixture spec's drawdown lines (test values; the live ones are the core spec's).
THIN_SPEC = copy.deepcopy(SYN_SPEC)
THIN_SPEC["risk"] = {**THIN_SPEC["risk"], "halve_drawdown": 0.12, "kill_drawdown": 0.18}
# `<state>/eod_equity.csv` (drawdown.py, THE SERIES), ending on the as-of date 2026-09-25.
# OK: 0.20% below the high; HALVE: 13.86%; KILL: 20.79%; STALE: the series ends a session
# early (UNMEASURED, its figures labelled with their own date); ABSENT: no file (UNMEASURED).
_EOD_HEAD = [("2026-09-21", 100000.0), ("2026-09-22", 101000.0), ("2026-09-23", 100500.0)]
EOD = {
    "ok": _EOD_HEAD + [("2026-09-24", 100600.0), ("2026-09-25", 100800.0)],
    "halve": _EOD_HEAD + [("2026-09-24", 95000.0), ("2026-09-25", 87000.0)],
    "kill": _EOD_HEAD + [("2026-09-24", 90000.0), ("2026-09-25", 80000.0)],
    "stale": _EOD_HEAD + [("2026-09-24", 100600.0)],
    "absent": None,
}
EOD_STATUS = {"ok": "OK", "halve": "HALVE", "kill": "KILL", "stale": "UNMEASURED",
              "absent": "UNMEASURED"}
THIN_EOD = ("ok", "halve", "absent")          # the pinned three
# A filled order in the account's history: the flat book is then not an opening session.
FILLED_BEFORE = [{"client_order_id": "cef-20260901-x", "filled_qty": "10", "symbol": "SYA"}]


def _digest(h: dict) -> str:
    return hashlib.sha256(json.dumps(h, sort_keys=True).encode()).hexdigest()


def _pin(h: dict) -> list:
    return [h["exit"], h.get("n_orders"), h.get("status"), _digest(h)]


def with_rule(spec: dict, rule: str) -> dict:
    """`spec` with frozen.below_min_names as `rule` ("absent": untouched), on a copy."""
    s = copy.deepcopy(spec)
    if rule != "absent":
        s["frozen"]["below_min_names"] = rule
    return s


def write_eod(state: Path, which: str) -> None:
    """`<state>/eod_equity.csv` for EOD[which]; nothing for "absent"."""
    state.mkdir(parents=True, exist_ok=True)
    rows = EOD[which]
    if rows is None:
        return
    lines = ["date,equity,change_usd"]
    prev = None
    for d, e in rows:
        lines.append(f"{d},{e},{'' if prev is None else round(e - prev, 2)}")
        prev = e
    (state / "eod_equity.csv").write_text("\n".join(lines) + "\n")


def thin_panel(base: Path, dst: Path, mp, n: int) -> None:
    """A copy of `base`'s panels at `dst` with exactly THIN_ELIGIBLE[:n] liquid on the as-of
    date (module docstring), and the sleeve pointed at it."""
    from src.deploy.sleeves import cef_discount as cefmod
    dst.mkdir(parents=True)
    P = pd.read_parquet(base / "cef_prices.parquet")
    dates = sorted(pd.to_datetime(P["date"]).unique())
    assert len(dates) == N_DAYS and pd.Timestamp(dates[-1]).date() == M.ASOF
    cut = dates[-THIN_SESSIONS]
    m = (~P["ticker"].isin(THIN_ELIGIBLE[:n])) & (pd.to_datetime(P["date"]) >= cut)
    P.loc[m, "volume"] = THIN_VOLUME
    P.to_parquet(dst / "cef_prices.parquet")
    pd.read_parquet(base / "cef_nav.parquet").to_parquet(dst / "cef_nav.parquet")
    mp.setattr(cefmod, "PX_PATH", dst / "cef_prices.parquet")
    mp.setattr(cefmod, "NAV_PATH", dst / "cef_nav.parquet")
    mp.setattr(cefmod, "GRP_PATH", dst / "cef_prices.parquet")


def thin_books(work: Path, mp) -> tuple:
    """(base panel dir, {"flat": {}, "held": half the complete panel's day-one book}). The
    held book is built with the key ABSENT on the complete panel, so every spec variant,
    te4's included, starts from the same shares."""
    base = M._synthetic_base(work, mp)
    M._scenario_panel(base, work / "complete_panel", mp, M.ASOF)
    held = M._held_book(SYN_SPEC, M.ASOF, SYN_SPEC["capital_usd"])
    assert any(q > 0 for q in held.values()) and any(q < 0 for q in held.values())
    return base, {"flat": {}, "held": held}


def thin_session(work: Path, spec, holdings: dict, eod: str, *, key=None, now=None,
                 execution=None, armed=False, client_attrs=None):
    """One thin-panel session (`M._session`) with `<state>/eod_equity.csv` as EOD[eod]. A flat
    book gets FILLED_BEFORE in its history (not an opening session). Returns M._session's
    (exit, state, client, log)."""
    write_eod(work / "state", eod)
    attrs = dict(client_attrs or {})
    if not holdings:
        attrs.setdefault("_closed", list(FILLED_BEFORE))
    return M._session(work, spec, holdings, now or M.EVE, execution or M.LATE_SCALE,
                      refresh_exit=0, key=key, armed=armed, account=attrs)


def _thin(work: Path, mp, spec, key) -> dict:
    """The THIN scenarios (module docstring), hashed as M._hashes hashes them."""
    base, books = thin_books(work, mp)
    out = {}
    for n in THIN_COUNTS:
        thin_panel(base, work / f"thin{n}" / "panel", mp, n)
        for book, holdings in books.items():
            for eod in THIN_EOD:
                w = work / f"thin{n}_{book}_{eod}"
                code, state, c, _ = thin_session(w, spec, holdings, eod, key=key)
                out[f"thin{n}|{book}|{eod}"] = M._hashes(w, state, code, c)
    return out


def _base_spec_bytes() -> bytes | None:
    """The core's frozen spec as of BASE_COMMIT (v9, no te4 key), or None."""
    r = subprocess.run(["git", "-C", str(rn.REPO), "show",
                        f"{BASE_COMMIT}:ops/specs/cef_discount.frozen.json"], capture_output=True)
    return r.stdout if r.returncode == 0 and r.stdout else None


def _real(work: Path, mp, spec_rule: str, key) -> dict | None:
    """The CORE scenarios on the real panel copy and BASE_COMMIT's spec; None when git cannot
    show the spec, or the copy or the spec is not what the pin was made on."""
    raw = _base_spec_bytes()
    if raw is None:
        return None
    base = work / "base"
    base.mkdir(parents=True)
    spec = json.loads(raw)
    got = {"panel": _frozen_copy(base, mp, spec["frozen"]["universe"]),
           "spec": hashlib.sha256(raw).hexdigest()}
    if got != REAL_PINNED_INPUT:
        return None
    return S._scenarios(work, base, mp, with_rule(spec, spec_rule), M.REAL_MISSING, key)


def _compact(d: dict) -> dict:
    return {k: _pin(v) for k, v in sorted(d.items())}


def print_pins():
    """Print every pin (module docstring, HOW THE PINS WERE MADE). Run with the key absent;
    the "flatten" variant is checked against the same pins."""
    import tempfile
    syn, real = {}, {}
    for label, key in KEYS.items():
        with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
            syn[label] = _compact(S._synthetic(Path(d) / "core", mp, SYN_SPEC, key))
        with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
            syn[label].update(_compact(_thin(Path(d) / "thin", mp, THIN_SPEC, key)))
        with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch.context() as mp:
            r = _real(Path(d) / "real", mp, "absent", key)
            real[label] = None if r is None else _compact(r)
    print("SYN_PINNED =", json.dumps(syn, indent=1, sort_keys=True))
    print("REAL_PINNED =", json.dumps(real, indent=1, sort_keys=True))


# The real-panel pin's input: test_combine_noop's frozen copy of the panels through 2026-09-25,
# and the sha256 of `git show 0b1a2ef...:ops/specs/cef_discount.frozen.json` (v9).
REAL_PINNED_INPUT = {
    "panel": COMBINE_PINNED_INPUT["panel"],
    "spec": "dd92e06d814ae6b89462348696da3dd537fcdb114c54bba6f37cc133eb55d313",
}
# PINNED 2026-11-03 on 0b1a2ef (module docstring), [exit, n_orders, status, digest]; identical
# unseeded and under PYTHONHASHSEED 1, on the laptop's dev panels (only rows through 2026-09-25 read).
SYN_PINNED = {
    'missing_nav_absent': {
        'complete|decide': [6, 7, "decided", "e83e236b8aecdba7cc7d372903336fc148d8f73c62c8da8cadc80b470120e787"],
        'complete|send': [0, None, None, "6cdf745aa4fddc6feb54edbfbb2fffb794925f1f62a98e9215c6ec6b79f52371"],
        'missing|eve': [11, 0, "refused", "7810a77290900417301e8b8216f041b08fc61ff84a99bddfd8441ff75cb7bff6"],
        'missing|final': [11, 0, "refused", "18d71508973ffb996b6634f448cdb637873410bfbde872fe14d1166869594cc1"],
        'missing|final_cls': [11, 0, None, "139e866ddc6b12686d8d4a48f952bab969a5a1f726741c7b2c7e512c64ebf20a"],
        'thin3|flat|absent': [3, 0, "decided", "15c06ee42f37bb1ad8a8c531e41c014ffe5f9ea48092ba42022fcbe137502dd1"],
        'thin3|flat|halve': [3, 0, "decided", "ab777cb0c78c231a7aba2f252bfbf6c5247c5ed865ea1431462e0381c3c048b6"],
        'thin3|flat|ok': [3, 0, "decided", "88088a996c23bb28292cd35346e29e0128037af0d655b77a6d8c35c7d0b5ceb7"],
        'thin3|held|absent': [6, 12, "decided", "1b0149c332931e6a2af87e4b3424fdf9e9e9fcbc718056721183419ae4be1406"],
        'thin3|held|halve': [6, 12, "decided", "6f09a6723eecfd9497dd9a9c474ebafebc62408c7aac0527c35f37cd541983e8"],
        'thin3|held|ok': [6, 12, "decided", "aafdd933233fc86a18e0924eff2e53603bef920660455827a80abaa1d99686cf"],
        'thin4|flat|absent': [3, 0, "decided", "3334e17855d702c035ea49010feb4202340e1b4f2681fa4732f246d8299bc929"],
        'thin4|flat|halve': [3, 0, "decided", "0151fd06c9194e9edf9a103119d38d6f81dd886092fead528b79f14ccecbf89f"],
        'thin4|flat|ok': [3, 0, "decided", "6bb5f455d6a57e9ca17b16a004e6b8a9bffb497193ded396cc7b035ceaca2d9d"],
        'thin4|held|absent': [6, 12, "decided", "5b9c22a156dff9d2fc8801e4efd614feda9fc6ba80aca7bacb6756e4a39fa0e1"],
        'thin4|held|halve': [6, 12, "decided", "4625edd2124dab94658018931496a7cca2ac570b3d7e59a10794b2dc393576dd"],
        'thin4|held|ok': [6, 12, "decided", "06ee79b03adc79ec22cdabe40ed1ec2f891d4474ec063116dc7c2deecd5fd00d"],
        'thin5|flat|absent': [3, 0, "decided", "b2897e2e8229a08754dc520a2baa633ca9c4f1ebcfc19e4c91fb0ea0e97baf83"],
        'thin5|flat|halve': [3, 0, "decided", "529cb0f7b0c22ab77e14c05fbd5b1d02558a1fa6557f8a8504583fcf8db0b9c8"],
        'thin5|flat|ok': [3, 0, "decided", "06b0e8b8b0e157ff34068a97af113bb935ed7565751010768dc5d563769f16f7"],
        'thin5|held|absent': [6, 12, "decided", "6f0413d2c13fce7291b588d0bc4eee4c5f0e69b436aba6768b65ed6ab6adbd7c"],
        'thin5|held|halve': [6, 12, "decided", "48960dfa8c1c23f08baa435218a0fe4cafe7580396e458952fcbc9910739afee"],
        'thin5|held|ok': [6, 12, "decided", "93d853f2677bb14b76cb44bf1534a4cb7611ea8420cdc39121b040cbe2fda0c5"],
    },
    'missing_nav_hold': {
        'complete|decide': [6, 7, "decided", "61af590df303c68eeb65a2f3023fb7c79eb9531cc1c0152c5cb8867ecf74ef0b"],
        'complete|send': [0, None, None, "6cdf745aa4fddc6feb54edbfbb2fffb794925f1f62a98e9215c6ec6b79f52371"],
        'missing|eve': [11, 0, "refused", "518d2b9ed01a4612019bad2ae8d1567f57b439a733855603f2fbc2a1a175c4c1"],
        'missing|final': [6, 6, "decided", "767a05ad92701b8172428236db4483d1024057ded1e352d0ff2b8e4cf02bcd8e"],
        'missing|final_cls': [0, 6, None, "798e996b4993f325899758ede8fd1169d5ba8778076f8ccb0c30a11390200d4b"],
        'thin3|flat|absent': [3, 0, "decided", "6165b8fef0c19bb5fb97fdbe0a08ce99cd9b77d887c7216d469fa589134188e2"],
        'thin3|flat|halve': [3, 0, "decided", "37cc7d6a69fe9446e618dcad1771a26325ab4b9229d51fc225872e12997606e2"],
        'thin3|flat|ok': [3, 0, "decided", "2ce954bcefc9862fde6e482053d75c840c88140df9f81672d83a7caef7e011a0"],
        'thin3|held|absent': [6, 12, "decided", "d667c001e70547a8055255358cdff7f5eb2a211eaec67c3b67f760b0ee6410ce"],
        'thin3|held|halve': [6, 12, "decided", "f0787dc5af90c40260c5c9c01391581a0ab2bc48f88fca68d78232ce2ae5f8ea"],
        'thin3|held|ok': [6, 12, "decided", "c9632cf8c6af8c0b9d02bd941ab3a64ef1b380c9c30d2a9a9eb45d654bbdb96f"],
        'thin4|flat|absent': [3, 0, "decided", "0fc6a6de69b77fdee64f07927e0362854345a9458b9a744facf50a5b8db9c398"],
        'thin4|flat|halve': [3, 0, "decided", "7f91a0efc46283b467653816df09378ceea6d97a25e2f6c2760ce2dc3ccd2665"],
        'thin4|flat|ok': [3, 0, "decided", "67ad9425eccc8655e42ee905718a6024feef02d82eb5312716523df7d2c227d2"],
        'thin4|held|absent': [6, 12, "decided", "f9a0895f7c442b8a0870da7046c692d993dff8f610b22429f07ec04dca754c24"],
        'thin4|held|halve': [6, 12, "decided", "9fc2e82dad8a24be3d60857612fcc2682e5cc96c09cf4538efc4549018659476"],
        'thin4|held|ok': [6, 12, "decided", "4d58f66517324bf95d4645e03181dd44284f7117e23552de244560764ff06595"],
        'thin5|flat|absent': [3, 0, "decided", "a19416595777b23b866c4fe8b0991969714a2295b47ce79c2e25b0af538b93f5"],
        'thin5|flat|halve': [3, 0, "decided", "90040fec6860ba5757c2bc2bf1c629485df90c9cda1208720084f29b51a15400"],
        'thin5|flat|ok': [3, 0, "decided", "13795be34b5edcb3e20b0ba3212907beb300b11c37cb8a589b6887b6236f7901"],
        'thin5|held|absent': [6, 12, "decided", "0dbe55abb7992ca30f005917bdf25c50f34215d572a2997925b6aa3f2d58353e"],
        'thin5|held|halve': [6, 12, "decided", "27f36c4d1a80ae406bb4b8b03dcf9e5defd0abc6201014caddf4a3d5fa6aa865"],
        'thin5|held|ok': [6, 12, "decided", "75fb1b639c7e7d357e246524a4f1cf509ced4837de5662ea969b6c51a3e56ae2"],
    },
}
REAL_PINNED = {
    'missing_nav_absent': {
        'complete|decide': [6, 6, "decided", "40184fb7f43fb2057081cbe5927a93a247806dcf11ced3a5f5fbb64ace0abc1c"],
        'complete|send': [0, None, None, "dc01e39abe7b96ea34fb4e2006e7a91e3f91fdd4e000f49b02b60f8360f2e429"],
        'missing|eve': [11, 0, "refused", "a02069360d9b1f349b1cbf24b305946b5b2377d2e574301ac51a028fa17cb44f"],
        'missing|final': [11, 0, "refused", "eb10a9a87836b5cfceff92f6d4346e74b1130e6a7464f7b8f1d1d76c53019c84"],
        'missing|final_cls': [11, 0, None, "b29309160d4839f639a6a60bd8d8c00266e2cb6b84f3db7c458abb583be22c5e"],
    },
    'missing_nav_hold': {
        'complete|decide': [6, 6, "decided", "54e416a47da69a81741714f59d36c39ddf3a4157a4308eb2f53aea15a03d3075"],
        'complete|send': [0, None, None, "dc01e39abe7b96ea34fb4e2006e7a91e3f91fdd4e000f49b02b60f8360f2e429"],
        'missing|eve': [11, 0, "refused", "1ebd87a75aedfee3b76277c4d0f715c6bbc8d95e72f008222fa32bd265e273fb"],
        'missing|final': [6, 6, "decided", "686a702763cbc0fff6fb683502b6cc9216037df7bbd28d6bccaa91e1e27bdf8e"],
        'missing|final_cls': [0, 6, None, "4f697c25646f2f682a690039d49922c7b55156aa25d1bb23cb1aac3d913b122c"],
    },
}


def _not_vacuous(got: dict, key):
    """The pins see what they claim to: the core scenarios decide and send as the sizing pin's
    do, and the thin sessions close the held book (FLAT targets, orders) and leave the flat
    book flat (nothing to send)."""
    assert got["complete|decide"][0] == rn.EXIT_PLANNED and got["complete|decide"][1] > 0
    assert got["complete|send"][0] == rn.EXIT_SENT
    if key is None:
        assert {got[f"missing|{x}"][0] for x in ("eve", "final", "final_cls")} == {rn.EXIT_REFUSED}
    else:
        assert got["missing|final"][0] == rn.EXIT_PLANNED
    for n in THIN_COUNTS:
        for eod in THIN_EOD:
            assert got[f"thin{n}|held|{eod}"][:3] == [rn.EXIT_PLANNED, got[f"thin{n}|held|{eod}"][1],
                                                     "decided"]
            assert got[f"thin{n}|held|{eod}"][1] > 0
            assert got[f"thin{n}|flat|{eod}"][0] == rn.EXIT_NOTHING
        # The drawdown record reached plan.json: the three digests differ.
        assert len({got[f"thin{n}|held|{eod}"][3] for eod in THIN_EOD}) == len(THIN_EOD)


def test_the_core_synthetic_pins_are_the_sizing_pins():
    """The core scenarios' digests made at 0b1a2ef equal those of test_sizing_multiplier_noop's
    SYN_PINNED, made at 35b429f: two independent bases, one book."""
    for label in KEYS:
        want = {k: _pin(v) for k, v in S.SYN_PINNED[label].items()}
        assert {k: SYN_PINNED[label][k] for k in want} == want


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("label", sorted(KEYS))
def test_synthetic_key_absent_and_flatten_are_0b1a2ef(tmp_path, monkeypatch, label, rule):
    key = KEYS[label]
    got = _compact(S._synthetic(tmp_path / "core", monkeypatch, with_rule(SYN_SPEC, rule), key))
    got.update(_compact(_thin(tmp_path / "thin", monkeypatch, with_rule(THIN_SPEC, rule), key)))
    assert got == SYN_PINNED[label]
    _not_vacuous(got, key)


def test_the_thin_sessions_read_the_drawdown_they_were_given(tmp_path, monkeypatch):
    """The eod fixtures do what the docstring says: the plan's drawdown status per EOD case."""
    base, books = thin_books(tmp_path, monkeypatch)
    thin_panel(base, tmp_path / "p", monkeypatch, 5)
    for eod in EOD:
        w = tmp_path / eod
        code, state, _, _ = thin_session(w, THIN_SPEC, books["held"], eod)
        assert code == rn.EXIT_PLANNED
        plan = M._plan(state)
        assert plan["drawdown"]["status"] == EOD_STATUS[eod], (eod, plan["drawdown"])
        assert "thin_session" not in plan and "thin_stops" not in plan
        assert {t["target"] for t in plan["targets"].values()} == {0}


def _skip_real(why_input: str):
    why = (f"REAL-PANEL TE4 NO-OP PIN NOT APPLIED: {why_input}. It was made on panel/spec "
           f"{REAL_PINNED_INPUT}, the spec read by `git show {BASE_COMMIT}:...`. The synthetic "
           f"pins still run")
    warnings.warn(why, RealPanelPinNotApplicable)
    pytest.skip(why)


@pytest.mark.skipif(not _real_panel_ready(), reason="real CEF panels absent (data/ is "
                                                     "gitignored); the synthetic pins still run")
@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("label", sorted(KEYS))
def test_real_panel_key_absent_and_flatten_are_0b1a2ef(tmp_path, monkeypatch, label, rule):
    from src.deploy.sleeves import cef_discount as cefmod
    real = {f: f.read_bytes() for f in (cefmod.PX_PATH, cefmod.NAV_PATH)}
    got = _real(tmp_path, monkeypatch, rule, KEYS[label])
    if got is None:
        _skip_real("git could not show the base spec, or this tree's panel copy differs")
    got = _compact(got)
    assert got == REAL_PINNED[label]
    assert got["complete|decide"][0] == rn.EXIT_PLANNED and got["complete|decide"][1] > 0
    assert got["complete|send"][0] == rn.EXIT_SENT
    assert all(f.read_bytes() == b for f, b in real.items()), "a real panel changed"
