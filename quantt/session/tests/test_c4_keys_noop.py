"""C4 step 1: the sleeve's four optional keys, ABSENT, leave the 13-name book byte-identical.

WHAT STEP 1 IS (`results/cef/C4_DEPLOY_PLAN_2026-10-27.md` §1 row 1, §2 step 1).
The `cef_discount` sleeve learns four optional frozen-spec keys so that trial C4
can later run as a SECOND spec of the same sleeve rather than as a copy of the
z-score: `panel_source`, `nav_repeat_mask` (M1), `zero_volume_mask` (M2) and
`below_min_names`. The live spec carries none of them, and the house rule is
that a new key must default to current behaviour, PROVED byte-for-byte
(CLAUDE.md; `/spec-change` step 3). The plan's §4 says it again for every C4
step: the 13's plan.json and `plan_sha` stay byte-identical until C4 is
switched on.

HOW IT IS PROVED, AND WHY THE PINS ARE PINS.

  1. `test_keys_absent_is_byte_identical_to_the_code_before_them`. The real
     sleeve, the core's pre-trial spec (below) and the real panels, decided as of 2026-09-25
     on a held book (half the day-one book, the `test_nav_gate.py` fixture, so
     the band both trades and holds), driven through `run_session` exactly as
     the drawdown and stale-NAV proofs drive it. Every output -- the day-one
     and held-book sleeve targets (reasons and 17-digit floats included, via
     `_fingerprint`), the exit code, the orders, the plan's targets, `plan_sha`
     and the plan.json bytes -- is hashed and compared with hashes COMPUTED BY
     THE SLEEVE AS IT WAS BEFORE THE KEYS EXISTED (66ec3df, `simon`), by running
     `_session_hashes` on that tree. The pins are those numbers, not
     expectations.

     THE SPEC IS THE CORE'S PRE-TRIAL ONE, FROM GIT (re-pinned 2026-11-02, as
     fb4671e did for test_combine_noop.py and test_missing_nav_hold.py). The
     pin was made on cef_discount.v7.20260928, which was then the live spec.
     CEF trial 53 made the live spec v8 (`sizing_multiplier` 1.13), and the
     test hashed the LIVE spec, so from eca5feb it skipped on every machine.
     66ec3df's code cannot run v8's key, so the code-versus-code proof stays
     on v7, read from git at 35b429f (test_combine_noop.pre_trial_spec; the
     same bytes as the local revert tag spec-cef_discount.v7.20260928). The
     pins are unchanged: they were made on these bytes. That the key-absent
     path is still today's on v8's code is test_sizing_multiplier_noop.py's.

     A pin is only a proof on the inputs it was made on. The panel is a
     refreshed vendor series (the 2026-10-15 refresh took in Yahoo's corrections
     of 2026-09-25, `test_nav_gate.py`), the prod VM's panel was captured at
     other times than the laptop's, and the spec may be bumped. So the
     test copies the panel rows it reads (the universe, through ASOF) into
     tmp_path in a canonical order, hashes that content and the spec, and
     SKIPS, naming both hashes, when either is not what the pin was made on.
     Skipping is the honest answer there: the old code's output on a different
     input is unmeasured, and comparing against it would be comparing against a
     number nobody computed.

  2. `test_keys_present_at_their_defaults_are_byte_identical_to_absent`. Runs
     on whatever real panel and live spec are present, so it never skips for a
     refresh: the live spec with the four keys ABSENT against the same spec with
     each key SET TO ITS DEFAULT (`panel_source` naming the `data/cef/` files,
     both masks `false`, `below_min_names` "flatten"). It keeps the absent path
     and the explicit-default path the same object after the pins have gone
     stale.

The synthetic tests of what each key DOES are in
`src/deploy/tests/test_c4_sleeve_keys.py`.

`data/` is gitignored: without the real panels both tests SKIP, naming the
file. Hermetic otherwise: test_run's FakeClient for the broker, a fixed clock,
no refresh, the stale-NAV gate and the drawdown check off (their own proofs
cover them), and netguard refuses any socket.
"""
import datetime as dt
import hashlib
import json
import warnings

import pandas as pd
import pytest

from quantt.session import run as rn
from quantt.session.tests.test_combine_noop import PRE_TRIAL_COMMIT, pre_trial_spec
from quantt.session.tests.test_run import BOOK, LATE, FakeClient
from src.deploy.tests.test_group_cap import _fingerprint

ET = rn.gt.ET
ASOF = dt.date(2026, 9, 25)                                  # a Friday; plans for Monday 09-28
EVE = dt.datetime(2026, 9, 25, 22, 0, tzinfo=ET)
SESSION_DIR = "2026-09-28"
LIVE_SPEC_PATH = rn.REPO / "ops/specs/cef_discount.frozen.json"
C4_KEYS = ("panel_source", "nav_repeat_mask", "zero_volume_mask", "below_min_names")


class RealPanelPinNotApplicable(UserWarning):
    """Emitted when the real-panel pin skips. A bare skip prints one `s` under
    `-q` and its reason only under `-rs`, so on the VM, or after a refresh that
    revised history, the pin stopped proving anything and nobody saw it (review
    of 11790b5). A warning lands in every run's warnings summary. The pin that
    never skips is `test_c4_synthetic_pin.py`."""


def _sha(x) -> str:
    return hashlib.sha256(x if isinstance(x, bytes) else x.encode()).hexdigest()


def _real_panel_ready() -> bool:
    from src.deploy.sleeves import cef_discount as cefmod
    return cefmod.PX_PATH.exists() and cefmod.NAV_PATH.exists()


needs_panel = pytest.mark.skipif(
    not _real_panel_ready(),
    reason="real CEF panels absent (data/ is gitignored); the synthetic tests in "
           "src/deploy/tests/test_c4_sleeve_keys.py still run")


def _frozen_copy(dst, monkeypatch, universe) -> str:
    """Copy the real panels' rows for `universe` dated at or before ASOF into `dst`,
    sorted (ticker, date) with a stable sort, and point the sleeve's module paths
    at the copy. Returns the sha256 of the copy's canonical content (dtypes and
    CSV text of both frames).

    WHY A COPY. Rows after ASOF and other tickers cannot reach a decision as of
    ASOF for this universe, but they CAN change from one refresh to the next; the
    copy keeps the pin's input exactly the rows the decision reads, so a refresh
    that only appends leaves the pin valid."""
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


def _session_hashes(work, spec, reasons=None) -> dict:
    """Every output of one decide, hashed: the sleeve's day-one and held-book
    targets, then a full `run_session` on the held book (the drawdown proof's
    deps, gate and check off). `work` is a fresh directory. `reasons`, a list
    if given, receives the held-book targets' reason strings, kept out of the
    hashed dict so the pins are exactly what the old code produced."""
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
    if reasons is not None:
        reasons.extend(t.reason for t in held_targets)

    state = work / "state"
    state.mkdir(parents=True)
    client = FakeClient(state, positions=held, clock_ts=EVE)
    client.long_mv = sum(q * closes[s] for s, q in held.items() if q > 0)
    client.short_mv = sum(q * closes[s] for s, q in held.items() if q < 0)
    client.maint = 0.5 * (client.long_mv - client.short_mv)         # fixture, not a measurement
    deps = rn.Deps(
        client=client, env={"QUANTT_STATE_DIR": str(state), "DRY_RUN": "0"},
        refresh=lambda a, t: rn.RefreshResult(exit=0, tail="fixture"),
        closes=lambda a, u: rn.last_closes(cefmod.PX_PATH, a, u),
        navs=lambda a, u: rn.last_navs(cefmod.NAV_PATH, a, u),
        targets=lambda a, h, eq, op, **kw: rn.sleeve_targets(spec, cap, a, h, eq, op, **kw),
        halts=lambda: [], utcnow=lambda: EVE.astimezone(dt.timezone.utc),
        out=type("O", (), {"write": lambda s, x: None, "flush": lambda s: None})(),
        execution={**LATE, "bp_shortfall": "scale"})
    code = rn.run_session(BOOK, spec, deps)
    raw = (state / SESSION_DIR / "plan.json").read_bytes()
    plan = json.loads(raw)
    return {"exit": code, "status": plan["status"], "n_orders": len(plan["orders"]),
            "band_holds": sum("band hold" in t["reason"] for t in plan["targets"].values()),
            "day_one_targets": _sha(_fingerprint(day1)),
            "held_targets": _sha(_fingerprint(held_targets)),
            "orders": _sha(json.dumps(plan["orders"], sort_keys=True)),
            "plan_targets": _sha(json.dumps(plan["targets"], sort_keys=True)),
            "plan_sha": plan["plan_sha"],
            "plan_json": _sha(raw)}


# PINNED 2026-10-27 by `_frozen_copy` + `_session_hashes` run on the sleeve and
# registry at 66ec3df (`simon`, before the four keys existed), on the laptop's
# dev panels (cef_prices to 2026-10-15, cef_nav to 2026-10-14; only rows through
# ASOF are read). Run twice in one process in two directories, and in three more
# processes under PYTHONHASHSEED 1, 2 and 3: identical every time, and identical
# again on the edited tree. Seed-independence matters here and is not automatic:
# where `max_gross_stress` BINDS on a held book the sleeve's weights depend on
# the hash seed in the last ulp (the band's `set(...) | set(...)` fixes the order
# `_cap_gross` sums in) -- 7 of 68 binding books in the commit's sweep, in the
# code before this change. The cap does not bind on this held book, and
# `test_keys_absent_is_byte_identical_to_the_code_before_them` asserts so.
PINNED_INPUT = {
    "panel": "3c614b42a0acf9ea570afba16f2c4defd990799a8c231d9cdd0c71f5daebcc7a",
    "spec": "c05035e55eaa89172f65d38a3485cb1c68123217177343b38576edf56583c02e",
}
PINNED = {
    "exit": 6,
    "status": "decided",
    "n_orders": 6,
    "band_holds": 6,
    "day_one_targets": "191edf1e76de87eb654a62068e69e1e250fffa9a64c6c19d8bbf1d99676f7d70",
    "held_targets": "c7107831e64c5968dda563d267c23a5c631168cb5525f1d60fbadd0b761f70eb",
    "orders": "f198dd92f1f473578190d104e61bd70d8bb2352ecb253bc12ccc6c9b23d75a2c",
    "plan_targets": "978e2df32387f0be9e49a3a5966369bed1866e780b1ca8d79d562d11f2c37f56",
    "plan_sha": "e69a46f6680840664ed3b44e21eb767cf4d9f641e0b3f9ee0fd07e45fa084e05",
    "plan_json": "410f7a4d24f97f08f533d8afe4c07736f277128816554474e19d8e74c9977fb8",
}


@needs_panel
def test_keys_absent_is_byte_identical_to_the_code_before_them(tmp_path, monkeypatch):
    pre = pre_trial_spec()
    if pre is None:
        why = (f"REAL-PANEL C4 NO-OP PIN NOT APPLIED: git cannot show "
               f"{PRE_TRIAL_COMMIT}:ops/specs/cef_discount.frozen.json, the spec the pin was made on")
        warnings.warn(why, RealPanelPinNotApplicable)
        pytest.skip(why)
    raw, spec = pre
    assert not set(C4_KEYS) & set(spec["frozen"]), \
        "the pre-trial spec carries a C4 key; this test proves the ABSENT path only"
    (tmp_path / "panels").mkdir()
    got_input = {"panel": _frozen_copy(tmp_path / "panels", monkeypatch, spec["frozen"]["universe"]),
                 "spec": _sha(raw)}
    if got_input != PINNED_INPUT:
        why = (f"REAL-PANEL C4 NO-OP PIN NOT APPLIED: it was made on panel/spec {PINNED_INPUT}; "
               f"this tree has {got_input} (a refresh revised rows through {ASOF}, another "
               f"machine's panel, or a spec bump). The old code's output on these inputs is "
               f"unmeasured. test_c4_synthetic_pin.py (never skips) and "
               f"test_keys_present_at_their_defaults_are_byte_identical_to_absent still run")
        warnings.warn(why, RealPanelPinNotApplicable)
        pytest.skip(why)
    from src.deploy.sleeves import cef_discount as cefmod
    assert cefmod.PX_PATH.parent == tmp_path / "panels"            # deciding on the copy
    held_reasons = []
    got = _session_hashes(tmp_path / "run", spec, held_reasons)
    assert got == PINNED
    # Not vacuous: the session decided, sent orders and kept band holds; and the
    # pin is seed-independent because the gross cap does not bind (see PINNED).
    assert got["exit"] == rn.EXIT_PLANNED and got["n_orders"] > 0 and got["band_holds"] > 0
    assert held_reasons and not any("*x" in r for r in held_reasons)


@needs_panel
def test_keys_present_at_their_defaults_are_byte_identical_to_absent(tmp_path):
    """The four keys SET TO THEIR DEFAULTS decide the same session as the keys
    absent, on whatever real panel and live spec this tree has (so it survives a
    refresh that retires the pins above). `panel_source` names the `data/cef/`
    files by their repo-relative paths, which is what the sleeve's module paths
    are; the real panels are read only, and must come out unchanged."""
    from src.deploy.sleeves import cef_discount as cefmod
    real = {f: f.read_bytes() for f in (cefmod.PX_PATH, cefmod.NAV_PATH)}
    spec = json.loads(LIVE_SPEC_PATH.read_text())
    explicit = json.loads(json.dumps(spec))
    explicit["frozen"].update({
        "panel_source": {"prices": cefmod.PX_PATH.relative_to(cefmod.REPO).as_posix(),
                         "nav": cefmod.NAV_PATH.relative_to(cefmod.REPO).as_posix()},
        "nav_repeat_mask": False, "zero_volume_mask": False, "below_min_names": "flatten"})
    assert explicit["frozen"]["panel_source"] == {"prices": "data/cef/cef_prices.parquet",
                                                  "nav": "data/cef/cef_nav.parquet"}
    absent = _session_hashes(tmp_path / "absent", spec)
    present = _session_hashes(tmp_path / "present", explicit)
    assert present == absent
    assert absent["exit"] == rn.EXIT_PLANNED and absent["n_orders"] > 0
    assert all(f.read_bytes() == b for f, b in real.items()), "a real panel changed"


# ------------------------------------------------- review of 11790b5: the runner and the skip

OTHER_PANEL = {"prices": "data/cef_c4/cef_prices.parquet", "nav": "data/cef_c4/cef_nav.parquet"}


def _on_another_panel():
    spec = json.loads(LIVE_SPEC_PATH.read_text())
    spec["frozen"]["panel_source"] = dict(OTHER_PANEL)
    return spec


def test_the_runner_reads_a_spec_on_another_panel_from_that_panel(tmp_path, monkeypatch):
    """Plan row 6A replaced the refusal this review added (`require_core_panel`):
    the runner now prices, gates and NAV-checks a spec on the panel its sleeve
    decides on (run.py PER-SLEEVE PANELS; behaviour in test_sleeve_panels.py).
    So a spec on `data/cef_c4/` is read from `data/cef_c4/`: `sleeve_targets`
    fails naming that file while it is absent, and is never handed the core's.
    And under the released book json, whose stale-NAV gate is the core panel's
    only, it is refused before any client is built."""
    from src.deploy.sleeves import cef_discount as cefmod
    monkeypatch.setattr(cefmod, "REPO", tmp_path)          # data/cef_c4 surely absent
    spec = _on_another_panel()
    assert rn.spec_panel(spec) == (tmp_path / OTHER_PANEL["prices"],
                                   tmp_path / OTHER_PANEL["nav"])
    with pytest.raises(FileNotFoundError, match="data/cef_c4/cef_prices.parquet"):
        rn.sleeve_targets(spec, 100_000.0, ASOF, {}, 100_000.0, True)
    with pytest.raises(rn.SessionError, match="data.stale_nav='report'.*cef_c4/cef_nav.parquet"):
        rn.default_deps(rn.BOOKS["cef"], spec, {"QUANTT_ENV_FILE": "unused"})


def test_the_runner_takes_the_core_spec_and_the_core_panel_named_explicitly():
    """The no-op: the live spec (no `panel_source`) and the same spec naming
    `data/cef/` explicitly are both read from the core panel, and refreshed by
    the core's command."""
    spec = json.loads(LIVE_SPEC_PATH.read_text())
    assert rn.spec_panel(spec) == rn.core_panel()
    spec["frozen"]["panel_source"] = {"prices": "data/cef/cef_prices.parquet",
                                      "nav": "data/cef/cef_nav.parquet"}
    assert rn.spec_panel(spec) == rn.core_panel()
    assert rn.refresh_flags(rn.spec_panel(spec)) == rn.CORE_REFRESH_FLAGS


def test_the_real_panel_pin_says_so_when_it_does_not_apply(tmp_path, monkeypatch):
    """A skip of the real-panel pin must be visible in a `-q` run, not only under
    `-rs`: it warns (RealPanelPinNotApplicable) as well as skipping."""
    import sys
    me = sys.modules[__name__]
    monkeypatch.setattr(me, "_frozen_copy", lambda dst, mp, universe: "a panel nobody pinned")
    with pytest.warns(RealPanelPinNotApplicable, match="PIN NOT APPLIED"):
        with pytest.raises(pytest.skip.Exception, match="PIN NOT APPLIED"):
            test_keys_absent_is_byte_identical_to_the_code_before_them(tmp_path, monkeypatch)
