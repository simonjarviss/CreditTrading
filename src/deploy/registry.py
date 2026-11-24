"""alloc_type -> Sleeve-class map + per-type spec validation.

  * `validate_spec(spec)` — structural accept/reject of a frozen spec.
    `ops.common.load_spec` delegates here.
  * `build_sleeve(spec, capital)` — instantiate the concrete Sleeve. Sleeve
    modules register themselves with `@register`.

TRIMMED 2026-09-28 (clean slate before the Alpaca build). Only the two types the
Alpaca system runs remain: `cef_discount` (the strategy) and `static_weights`
(the b6 benchmark). The credit_rv, null_trader, forced-flow tracker and
declared-but-unimplemented types went with their sleeves; the full file is at
tag `pre-clean-slate`.
"""

CEF_DISCOUNT_ALLOC_TYPE = "cef_discount"

ALLOWED_ALLOC_TYPES = {"static_weights", CEF_DISCOUNT_ALLOC_TYPE}

WEIGHT_EXPRESSIBLE = {"static_weights"}

_REGISTRY = {}


def register(cls):
    """Class decorator: register a Sleeve subclass under its `alloc_type`."""
    at = getattr(cls, "alloc_type", "")
    if at not in ALLOWED_ALLOC_TYPES:
        raise ValueError(f"cannot register sleeve with unknown alloc_type {at!r}")
    _REGISTRY[at] = cls
    return cls


def registered_types():
    return set(_REGISTRY)


def is_weight_expressible(alloc_type) -> bool:
    return alloc_type in WEIGHT_EXPRESSIBLE


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _require(spec, key, where="spec"):
    if key not in spec:
        raise ValueError(f"{where} missing required key {key!r}")
    return spec[key]


def _require_dict(spec, key, where="spec"):
    v = _require(spec, key, where)
    if not isinstance(v, dict):
        raise ValueError(f"{where}[{key!r}] must be an object, got {type(v).__name__}")
    return v


def _validate_capital(spec):
    cap = spec.get("capital_usd", spec.get("book_usd"))
    if cap is None:
        raise ValueError("spec missing capital_usd (or book_usd)")
    cap = float(cap)
    band = spec.get("capital_band") or spec.get("book_usd_band")
    if band is not None:
        lo, hi = float(band[0]), float(band[1])
        if not (lo <= cap <= hi):
            raise ValueError(
                f"capital_usd {cap:.0f} outside capital_band [{lo:.0f}, {hi:.0f}]")
    return cap


def _validate_common(spec):
    _require(spec, "spec_id")
    _require(spec, "status")
    alloc = _require_dict(spec, "allocation")
    t = _require(alloc, "type", "allocation")
    if t not in ALLOWED_ALLOC_TYPES:
        raise ValueError(f"unsupported allocation type {t!r}")
    _validate_capital(spec)
    return t


def _validate_static_weights(spec):
    alloc = spec["allocation"]
    w = _require_dict(alloc, "weights", "allocation")
    if not w:
        raise ValueError("static_weights allocation has no weights")
    total = 0.0
    for k, v in w.items():
        fv = float(v)
        if fv < 0:
            raise ValueError(
                f"weight for {k!r} is {fv} < 0. This simulator does not short; "
                "a short leg needs the derivatives ledger, not static_weights.")
        total += fv
    if total > 1.0 + 1e-9:
        raise ValueError(
            f"static_weights weights sum to {total:.4f} > 1.0. This path does "
            "not borrow; wire the financing leg first.")


# ---------------------------------------------------------------------------
# cef_discount: the four optional keys that let a second spec reuse the sleeve
# ---------------------------------------------------------------------------
#
# WHY THEY EXIST (C4 deployment plan, results/cef/C4_DEPLOY_PLAN_2026-10-27.md
# §1 row 1). Trial C4 ran THIS sleeve's z-score on 74 other funds through
# `band_frontier.build_targets(universe=, source=, mask=)`, and the plan reuses
# the sleeve with a second frozen spec rather than writing a second copy of the
# z-score (two copies of a signal agree until one of them is edited). The trial
# differs from the sleeve in exactly three ways the sleeve could not express:
# where its panels live, two masks on the discount (PREREG_C4_FAMILIES §4.3),
# and what it does below `min_names` (`build_targets` holds; the sleeve
# flattens). These keys express them.
#
# ABSENT IS TODAY'S BEHAVIOUR, BYTE FOR BYTE, for every one of them, and the
# live spec carries none (`quantt/session/tests/test_c4_keys_noop.py` pins the
# 13's plan.json and plan_sha against the code before the keys existed). The
# parse lives HERE, once: `_validate_cef_discount` calls it on the spec, and the
# sleeve calls it again on its own `frozen` block, so a sleeve built without the
# registry still cannot read a value the registry would refuse.
#
# NO NULL, NO TRUTHINESS. Unlike `band_width`, whose null means off, a present
# key must hold one of its declared values: `null`, `1`, `"true"` or a typo
# raises, naming the key and the value. A key that decides whether a fund has a
# discount, or whether the book is closed, must not be decided by Python
# truthiness or by a spelling.

CEF_PANEL_SOURCE_KEYS = ("prices", "nav")
CEF_MASK_KEYS = ("nav_repeat_mask", "zero_volume_mask")
# "trade_eligible" (CEF trial 55, te4, PAPER ONLY; results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md)
# needs `below_min_names_floor` (`cef_below_min_names_floor`) and, in the sleeve, a paper declaration.
CEF_BELOW_MIN_NAMES = ("flatten", "hold", "trade_eligible")       # the first is the default


def cef_panel_source(frozen):
    """`panel_source` as (prices, nav) repo-relative POSIX strings, or None when absent.

    The value is `{"prices": "<path>", "nav": "<path>"}`, each relative to the
    repository root -- the root of the prod clone, so one spec names the same
    file on the laptop and on the VM. An absolute path would name one machine's
    disk inside a governance object, and `..` would let a spec read outside
    the clone; both raise. Each must be a `.parquet` in the live panels' schema
    (`date ... close volume ticker grp` / `date nav ticker`, as `data/cef/` and
    `data/cef_families/` are built), and the two must differ: a price file read
    as NAV would give every fund a discount of zero, which is a book, not an
    error.
    """
    if "panel_source" not in frozen:
        return None
    v = frozen["panel_source"]
    if not isinstance(v, dict):
        raise ValueError(f"cef_discount panel_source must be an object "
                         f"{{'prices': <path>, 'nav': <path>}}, got {v!r}")
    unknown = sorted(set(v) - set(CEF_PANEL_SOURCE_KEYS))
    missing = [k for k in CEF_PANEL_SOURCE_KEYS if k not in v]
    if unknown or missing:
        raise ValueError(f"cef_discount panel_source has unknown key(s) {unknown} and lacks "
                         f"{missing}; it takes exactly {list(CEF_PANEL_SOURCE_KEYS)}")
    from pathlib import PurePosixPath
    out = []
    for k in CEF_PANEL_SOURCE_KEYS:
        p = v[k]
        if not isinstance(p, str) or not p.strip() or p != p.strip():
            raise ValueError(f"cef_discount panel_source[{k!r}] must be a non-empty path "
                             f"string without surrounding space, got {p!r}")
        pp = PurePosixPath(p)
        if pp.is_absolute() or "\\" in p or ".." in pp.parts:
            raise ValueError(f"cef_discount panel_source[{k!r}] = {p!r}: must be relative to "
                             f"the repository root, with '/' and no '..'")
        if pp.suffix != ".parquet":
            raise ValueError(f"cef_discount panel_source[{k!r}] = {p!r}: not a .parquet file")
        out.append(str(pp))
    if out[0] == out[1]:
        raise ValueError(f"cef_discount panel_source names {out[0]!r} for both prices and nav")
    return tuple(out)


def cef_mask_flag(frozen, key):
    """`nav_repeat_mask` / `zero_volume_mask`: exactly true or false; absent is false."""
    if key not in CEF_MASK_KEYS:
        raise KeyError(f"{key!r} is not a cef_discount mask key {CEF_MASK_KEYS}")
    if key not in frozen:
        return False
    v = frozen[key]
    if v is not True and v is not False:
        raise ValueError(f"cef_discount {key} must be exactly true or false, got {v!r} "
                         f"({type(v).__name__})")
    return v


def cef_below_min_names(frozen):
    """`below_min_names`: "flatten" (absent; today's rule), "hold" (trial C4's) or
    "trade_eligible" (CEF trial 55's, paper only: build on the eligible names when at
    least `below_min_names_floor` of them are; `cef_below_min_names_floor`)."""
    if "below_min_names" not in frozen:
        return CEF_BELOW_MIN_NAMES[0]
    v = frozen["below_min_names"]
    if not isinstance(v, str) or v not in CEF_BELOW_MIN_NAMES:
        raise ValueError(f"cef_discount below_min_names {v!r} is not one of "
                         f"{list(CEF_BELOW_MIN_NAMES)}")
    return v


CEF_FLOOR_KEY = "below_min_names_floor"


def cef_below_min_names_floor(frozen):
    """`below_min_names_floor` as an int, or None when the thin-session rule does not read it.

    WHAT IT IS (CEF trial 55, "te4", results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md
    §1.1, approved 2026-11-03, PAPER ONLY). Under `below_min_names = "trade_eligible"`, a
    session with fewer than `min_names` eligible funds but at least this many builds the book
    on the eligible funds with the sleeve's own construction; below it the book goes FLAT, as
    under "flatten". It is the harness's `floor` argument
    (`scripts/cef/band_frontier.py::band_gross_capped`), with the harness's checks.

    UNITS: a COUNT of eligible funds. Not a weight, not a fraction.

    WHEN IT IS READ. Required when, and only when, `below_min_names` is "trade_eligible":
    there it has no default, because the spec is the only authority on a live parameter
    (CLAUDE.md) and a floor the sleeve invented would be one no derivation produced. Under
    "flatten", "hold" or the key absent it is REFUSED, as the harness refuses `floor`: a floor
    that nothing reads is a spec that says one thing and trades another, and an absent
    `below_min_names` (flatten) with a floor beside it is most likely a half-applied edit.
    Its note `_below_min_names_floor_note` is refused there too, naming it (review of 4e1ab0b):
    the revert deletes the floor and its note, and a note left behind would otherwise load
    cleanly in a spec that is then not byte-identical to the pre-te4 one.

    REFUSED, naming the value: a bool (JSON `true` is not 1 fund), any non-int (4.0 included:
    the harness takes an int, and a float that happens to be whole is a typed-by-hand
    number), anything below 2 (one name is z - mean(z) = 0, so the weights are 0/0), and
    anything at or above `min_names` (at `min_names` the rule IS flatten). It does NOT
    hard-code 4: the derivation's reason for 4 belongs in the spec's note. A missing or
    non-integer `min_names` raises here too, because the upper bound cannot be checked
    without it. A misspelling (`below_min_names_flor`) is refused by `cef_optional_keys`,
    whose near-miss guard lists this key (CEF_C4_KEYS).

    READ BY `_validate_cef_discount` (a bad floor refuses the spec at load) and the sleeve's
    constructor (so a sleeve built without the registry refuses it too, on every day, not
    only on the first thin one). `cef_optional_keys`' returned dict does NOT carry it: that
    dict is pinned (`scripts/cef/tests/test_c4_paper_benchmark.py`) and describes C4's keys.
    """
    rule = cef_below_min_names(frozen)
    present = CEF_FLOOR_KEY in frozen
    note = f"_{CEF_FLOOR_KEY}_note"
    if rule != "trade_eligible":
        if present:
            raise ValueError(
                f"cef_discount {CEF_FLOOR_KEY} is set ({frozen[CEF_FLOOR_KEY]!r}) but "
                f"below_min_names is {rule!r}"
                + (" (absent)" if "below_min_names" not in frozen else "")
                + "; the floor is read only under 'trade_eligible'. Delete it, or set "
                  "below_min_names to 'trade_eligible'")
        # The floor's NOTE, left behind (review of 4e1ab0b). te4's revert deletes the floor
        # and its note, and the reverted spec must be byte-identical to the pre-te4 one
        # (docs/RUNNER.md, te4's revert). A note nothing documents is the trace of a half-done
        # revert, and nothing else would catch it: refused, as the floor is.
        if note in frozen:
            raise ValueError(
                f"cef_discount {note} is set but below_min_names is {rule!r}"
                + (" (absent)" if "below_min_names" not in frozen else "")
                + f"; it documents {CEF_FLOOR_KEY}, which is read only under 'trade_eligible'. "
                  f"Delete it with the floor, or set below_min_names to 'trade_eligible'")
        return None
    if not present:
        raise ValueError(
            f"cef_discount below_min_names 'trade_eligible' needs {CEF_FLOOR_KEY}, the "
            f"smallest eligible count it trades; it has no default")
    v = frozen[CEF_FLOOR_KEY]
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"cef_discount {CEF_FLOOR_KEY} must be an int (a count of eligible "
                         f"funds), got {v!r} ({type(v).__name__})")
    if "min_names" not in frozen:
        raise ValueError(f"cef_discount {CEF_FLOOR_KEY} {v} cannot be checked: the spec has no "
                         f"min_names, its upper bound")
    mn = frozen["min_names"]
    if isinstance(mn, bool) or not isinstance(mn, (int, float)) or int(mn) != mn:
        raise ValueError(f"cef_discount min_names {mn!r} is not a whole number; "
                         f"{CEF_FLOOR_KEY} cannot be checked against it")
    if not 2 <= v < int(mn):
        raise ValueError(f"cef_discount {CEF_FLOOR_KEY} {v} must satisfy 2 <= floor < min_names "
                         f"({int(mn)}): one name is 0/0, and at min_names the rule is 'flatten'")
    return v


CEF_C4_KEYS = ("panel_source", *CEF_MASK_KEYS, "below_min_names", CEF_FLOOR_KEY)
# A key's documentation sibling, in the spec's own convention (`_band_width_note`).
CEF_C4_NOTES = tuple(f"_{k}_note" for k in CEF_C4_KEYS)
# How far a frozen key may be from one of these and still be read as a
# misspelling of it: 2 edits (insert, delete, substitute or swap two adjacent
# letters) covers a plural, a dropped or doubled letter and a transposition.
# Every key the live spec carries is at least 6 edits from all of them
# (`test_c4_sleeve_keys.py` checks the live file, key by key). The fifth,
# `below_min_names_floor` (CEF trial 55, te4), is not one of C4's but rides the
# same guard: absent under "trade_eligible" refuses, so a misspelt floor would
# refuse anyway, but under any other rule a misspelt floor would be silently
# ignored where the correctly spelt one is refused.
CEF_C4_NEAR = 2


def _osa_distance(a: str, b: str) -> int:
    """Optimal-string-alignment edit distance: insertions, deletions,
    substitutions and adjacent transpositions, each costing 1."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def cef_c4_near_miss(key: str):
    """The C4 key that `key` looks like a misspelling of, or None.

    WHY (review of 11790b5). An absent C4 key means "today's behaviour", so a
    misspelt one is silently absent: `nav_repeat_masks: true` validated, and the
    sleeve then ran WITHOUT the mask the spec plainly asks for; `below_min_name:
    "hold"` flattened the book the spec says to hold. Rejecting every unknown key
    would reject keys other specs and the live one legitimately carry (notes,
    `warmup_days`), so only near-misses of the four new names are refused:

      * within CEF_C4_NEAR edits of one of them, after lower-casing and reading
        `-` and spaces as `_`;
      * the same letters with the underscores dropped (`navrepeatmask`);
      * one of them dressed as a comment (`_nav_repeat_mask`): in this spec's
        convention a leading underscore is a note nothing reads, so the key
        would be ignored while reading as set. Absent is the default; delete it.

    `below_min_names_floor` (CEF trial 55) is checked the same way, as the
    fifth name in CEF_C4_KEYS.

    A `_<key>_note` sibling is not a miss, and a misspelt note is checked as its
    stem (`_nav_repeat_masks_note` is a miss of `nav_repeat_mask`).
    """
    if key in CEF_C4_KEYS or key in CEF_C4_NOTES or not isinstance(key, str):
        return None
    stem = key.strip().lower().replace("-", "_").replace(" ", "_").strip("_")
    if stem.endswith("_note"):
        stem = stem[:-len("_note")].strip("_")
    for k in CEF_C4_KEYS:
        if (stem == k or stem.replace("_", "") == k.replace("_", "")
                or _osa_distance(stem, k) <= CEF_C4_NEAR):
            return k
    return None


def cef_optional_keys(frozen) -> dict:
    """All four C4 keys parsed, each to its default when absent. Raises on the
    first malformed one, and on a frozen key that is a near-miss of one of them
    or of `below_min_names_floor` (`cef_c4_near_miss`). Called by
    `_validate_cef_discount` and by the sleeve's constructor, so a bad
    `below_min_names` refuses on every day and not only on the first day the
    book falls below `min_names`. The returned dict is C4's four and is pinned
    (`scripts/cef/tests/test_c4_paper_benchmark.py`); the floor is parsed by
    `cef_below_min_names_floor`, beside this call in both callers."""
    for key in frozen:
        k = cef_c4_near_miss(key)
        if k is not None:
            raise ValueError(
                f"cef_discount frozen key {key!r} looks like a misspelling of {k!r}; the "
                f"sleeve would ignore it and run {k}'s default. Spell it {k!r}, or delete "
                f"it (absent is the default)")
    return {"panel_source": cef_panel_source(frozen),
            **{k: cef_mask_flag(frozen, k) for k in CEF_MASK_KEYS},
            "below_min_names": cef_below_min_names(frozen)}


# ---------------------------------------------------------------------------
# CEF trial 55 (te4): the K1-K3 report thresholds, in the spec's `risk` block
# ---------------------------------------------------------------------------

# Each is a line the K1-K3 REPORT reads (quantt/session/drawdown.py `thin_stop_record`);
# nothing trades on any of them (pre-registration §6.3: "No code acts on them"; the team lead
# acts, through the revert spec). Units and the pre-registration's drafting-day values:
CEF_THIN_STOP_KEYS = (
    "thin_k1_episode_drawdown",   # K1: a FRACTION of the episode's high-water mark (D_E, 0.1052)
    "thin_k2_max_name_frac",      # K2: largest |name market value| / equity (0.956)
    "thin_k3_net_run",            # K3: |long - short| / equity, on CEF_THIN_K3_RUN_KEY reduced closes in a row (0.248)
    "thin_k3_net_once",           # K3: |long - short| / equity, once (0.833)
)
# The provenance a threshold must carry: the file of `results/cef/prereg_thin_te4/compose.py`'s
# run on the read date that derived it (H14; the owner's answer 3, 2026-11-03).
CEF_THIN_STOP_SOURCE = "compose_"
# K3's persistence: how many reduced closes in sequence above `thin_k3_net_run` trip K3 (§6.3:
# "above the fit p99 on 3 consecutive reduced sessions"). A COUNT, not a share of equity. It was
# a module constant in quantt/session/drawdown.py until the runner owner's review of 2026-11-04
# (item 9): a stop's rule belongs in the frozen spec, the only authority on a live parameter.
CEF_THIN_K3_RUN_KEY = "thin_k3_run_sessions"
# Every te4 key in the `risk` block: the misspelling guard and the other-rule refusal read all five.
CEF_THIN_KEYS = (*CEF_THIN_STOP_KEYS, CEF_THIN_K3_RUN_KEY)


def _thin_stop_near_miss(key: str):
    """The te4 `risk` key (CEF_THIN_KEYS: a K-line threshold or K3's run length) `key` is, or
    looks like a misspelling of, or None (`cef_c4_near_miss`'s rule, CEF_C4_NEAR edits). A
    `_<key>_note` is checked as its stem, so a note is a match of its own key."""
    stem = key.strip().lower().replace("-", "_").replace(" ", "_").strip("_")
    if stem.endswith("_note"):
        stem = stem[:-len("_note")].strip("_")
    for k in CEF_THIN_KEYS:
        if (stem == k or stem.replace("_", "") == k.replace("_", "")
                or _osa_distance(stem, k) <= CEF_C4_NEAR):
            return k
    return None


def cef_thin_stop_levels(spec) -> dict:
    """{key: float | None} for CEF_THIN_STOP_KEYS, from `spec["risk"]`, None where absent, and
    CEF_THIN_K3_RUN_KEY: int | None (None only when `below_min_names` is not "trade_eligible").

    WHAT THEY ARE (CEF trial 55, "te4", results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md
    §6.3; the runner's owner, answer 3, 2026-11-03). The thresholds of the K1-K3 report lines
    that the activation release must carry. They are REPORT-ONLY spec keys: the activation
    commit sets them, each re-measured on its read date by `compose.py --stamp <date>`, and a
    report line whose key is absent reads UNMEASURED, never a default. The live path never
    reads `results/`, so the value lives here, with its provenance beside it.

    REFUSED, naming the key and the value:
      * a key present while `below_min_names` is not "trade_eligible": a threshold nothing
        reads is a spec that says one thing and does another (the floor's rule,
        `cef_below_min_names_floor`). The revert spec deletes them with the floor;
      * likewise any of their notes `_<key>_note` (the five CEF_THIN_KEYS') under another
        rule, named (review of 4e1ab0b). The revert deletes each key with its note, and the
        reverted spec must be byte-identical to the pre-te4 one (docs/RUNNER.md, te4's
        revert); a note skipped by the misspelling guard and not counted here would load
        cleanly, so only a manual diff would have caught it;
      * a key without its sibling note `_<key>_note`, or a note that does not name the
        `compose_<stamp>.json` that derived it: a threshold without provenance is a rumour
        (CLAUDE.md, data rules), and H14 requires that it was re-measured;
      * a bool or a non-number, NaN or inf, or zero or below;
      * `thin_k1_episode_drawdown` at or above 1: a drawdown line is a FRACTION, and 10.52
        is a percent written where a fraction belongs (drawdown.py `levels`, the units trap);
      * the three exposure lines at or above `frozen.max_gross_stress`: each is a share of
        equity that the account's own gross cap bounds at the decision (a single name, or
        the net, is at most the gross), so a value at or above the cap is unreachable but by
        drift, and 95.6 is a percent; and `max_gross_stress` absent, since then there is no
        bound to check against;
      * `thin_k3_net_run` not below `thin_k3_net_once`: the persistent line is the lower one
        (p99 against the fit maximum), or the run rule could never fire first;
      * a key in `risk` that looks like a misspelling of one of them (`cef_c4_near_miss`'s
        rule: within CEF_C4_NEAR edits, the letters without underscores, or a `_comment`):
        absent reads UNMEASURED, so a misspelt key would leave the line unread while the spec
        reads as set.

    K3'S RUN LENGTH, `risk.thin_k3_run_sessions` (CEF_THIN_K3_RUN_KEY; the runner owner's
    review 2026-11-04, item 9). K3 trips on this many reduced closes in sequence above
    `thin_k3_net_run` (§6.3: 3). It is the stop's rule, not a measured level, so unlike the four
    lines it is REQUIRED whenever `below_min_names` is "trade_eligible", with no default:
    absent there refuses the spec, as an absent floor does (`cef_below_min_names_floor`), and a
    K3 whose rule the code supplied would be a rule no spec states. Present under any other
    rule (absent, "flatten", "hold") it is refused, as the lines are. It must be an int (a
    bool, a float, 3.0 included, or a string refuses) of at least 2: one close above the line
    is the once rule's business, and a "run" of 1 would make the run line a second once line.
    Its sibling `_thin_k3_run_sessions_note` is required, a non-empty string saying where the
    count comes from (it is pre-registered in §6.3, not derived by compose.py, so the
    compose_<stamp>.json rule of the four lines does not apply to it). The activation commit
    sets it; quantt/session/drawdown.py reads it from the thresholds passed in, never a
    constant of its own.
    """
    risk = spec.get("risk")
    if risk is None:
        risk = {}
    if not isinstance(risk, dict):
        raise ValueError(f"spec risk block is {type(risk).__name__}, not an object")
    notes = tuple(f"_{k}_note" for k in CEF_THIN_KEYS)
    for key in risk:
        if not isinstance(key, str) or key in CEF_THIN_KEYS or key in notes:
            continue
        k = _thin_stop_near_miss(key)
        if k is not None:
            raise ValueError(
                f"cef_discount risk key {key!r} looks like a misspelling of {k!r}; its K-line "
                f"would read UNMEASURED while the spec reads as set. Spell it {k!r}, or "
                f"delete it")
    # In the wrong block: `frozen` is not where these are read, so one written there would be
    # ignored as silently as a misspelt one.
    for key in (spec.get("frozen") or {}):
        k = _thin_stop_near_miss(key) if isinstance(key, str) else None
        if k is not None:
            raise ValueError(f"cef_discount frozen key {key!r} is (or looks like) the K-line "
                             f"threshold {k!r}, which is read from the spec's `risk` block only; "
                             f"move it to risk.{k}")
    out = {k: None for k in CEF_THIN_KEYS}
    present = [k for k in CEF_THIN_KEYS if k in risk]
    frozen = spec.get("frozen") or {}
    rule = cef_below_min_names(frozen)
    if rule != "trade_eligible":
        # The keys and their notes alike (the notes since the review of 4e1ab0b: a note left
        # by a revert is otherwise skipped by the guard above and loads cleanly).
        stray = present + [n for n in notes if n in risk]
        if stray:
            raise ValueError(f"cef_discount risk {stray} set but below_min_names is {rule!r}; "
                             f"the K1-K3 lines, K3's run length and their notes are read only "
                             f"under 'trade_eligible'. Delete them, or set the rule")
        return out
    rk = CEF_THIN_K3_RUN_KEY
    if rk not in risk:
        raise ValueError(f"cef_discount below_min_names 'trade_eligible' needs risk.{rk}, the "
                         f"number of reduced closes in sequence above thin_k3_net_run that trips "
                         f"K3 (pre-registration §6.3); it has no default")
    v = risk[rk]
    if isinstance(v, bool) or not isinstance(v, int):
        raise ValueError(f"cef_discount risk.{rk} must be an int (a count of reduced closes), "
                         f"got {v!r} ({type(v).__name__})")
    if v < 2:
        raise ValueError(f"cef_discount risk.{rk} {v} must be at least 2: one close above the "
                         f"line is the once rule's (thin_k3_net_once)")
    note = risk.get(f"_{rk}_note")
    if not (isinstance(note, str) and note.strip()):
        raise ValueError(f"cef_discount risk.{rk} needs its sibling note _{rk}_note saying where "
                         f"the count comes from; got {note!r}")
    out[rk] = v
    present = [k for k in CEF_THIN_STOP_KEYS if k in risk]
    import math
    cap = frozen.get("max_gross_stress")
    for k in present:
        v = risk[k]
        note = risk.get(f"_{k}_note")
        if not (isinstance(note, str) and CEF_THIN_STOP_SOURCE in note and ".json" in note):
            raise ValueError(f"cef_discount risk.{k} needs its sibling note _{k}_note naming the "
                             f"{CEF_THIN_STOP_SOURCE}<stamp>.json that derived it (H14: re-measured "
                             f"on the read date); got {note!r}")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) \
                or not v > 0:
            raise ValueError(f"cef_discount risk.{k} {v!r} must be a finite number above 0")
        if k == "thin_k1_episode_drawdown":
            if not v < 1:
                raise ValueError(f"cef_discount risk.{k} {v!r}: a drawdown line is a FRACTION of "
                                 f"the high-water mark, in (0, 1); {v!r} reads as a percent. "
                                 f"Refused, not rescaled")
        else:
            if isinstance(cap, bool) or not isinstance(cap, (int, float)) or not math.isfinite(cap):
                raise ValueError(f"cef_discount risk.{k} cannot be checked: frozen."
                                 f"max_gross_stress is {cap!r}")
            if not v < cap:
                raise ValueError(f"cef_discount risk.{k} {v!r} is not below max_gross_stress "
                                 f"{cap}: a share of equity the gross cap bounds at the decision; "
                                 f"a percent written where a fraction belongs?")
        out[k] = float(v)
    run, once = out["thin_k3_net_run"], out["thin_k3_net_once"]
    if run is not None and once is not None and not run < once:
        raise ValueError(f"cef_discount risk.thin_k3_net_run {run} must be below "
                         f"thin_k3_net_once {once}")
    return out


# ---------------------------------------------------------------------------
# sizing_multiplier (CEF trial 53, results/cef/PREREG_VOLTARGET_2026-10-30.md)
# ---------------------------------------------------------------------------

CEF_SIZING_KEY = "sizing_multiplier"


def cef_sizing_multiplier(frozen):
    """`sizing_multiplier` as a float, or None when absent or null (today's book).

    WHAT IT IS. The account holds m times the sleeve's UNIT book: the book this
    spec builds at its own `vol_target_annual`. The band compares the unit target
    with held / m, `_cap_gross` acts at `max_gross_stress / m` in unit weights
    (so at `max_gross_stress` x the account's NAV), and every weight target is
    emitted as m x the unit weight (src/deploy/sleeves/cef_discount.py,
    `target_positions`). `vol_target_annual` is NOT moved. C4's fidelity gate
    (scripts/cef/c4_paper_benchmark.py on its branches) compares the sleeve's `w`
    at the `min_abs_weight` read with the trial's T, and names that key and
    `gross_leverage` as its negative controls; the unit book is that `w`,
    untouched. Every research reader of `spec.VOL_TARGET` stays on the unit book
    too.

    UNITS: a multiple of the unit book. Not a percent, not a vol. 1.13 means
    13% larger.

    REFUSED, naming the value: a bool, a string or any non-number, NaN or inf,
    and zero or below. A frozen key that looks like a misspelling of it
    (`cef_c4_near_miss`'s rule: within CEF_C4_NEAR edits, the same letters
    without underscores, or dressed as a `_comment`) also raises. Absent is
    today's book, so a misspelt key would size the book at 1.0 while the spec
    reads as raised. The cross-key checks (the cap must be set, and the effective
    vol target must stay in the sane band) are in `_validate_cef_discount`.
    """
    note = f"_{CEF_SIZING_KEY}_note"
    for key in frozen:
        if not isinstance(key, str) or key in (CEF_SIZING_KEY, note):
            continue
        stem = key.strip().lower().replace("-", "_").replace(" ", "_").strip("_")
        if stem.endswith("_note"):
            stem = stem[:-len("_note")].strip("_")
        if (stem == CEF_SIZING_KEY or stem.replace("_", "") == CEF_SIZING_KEY.replace("_", "")
                or _osa_distance(stem, CEF_SIZING_KEY) <= CEF_C4_NEAR):
            raise ValueError(
                f"cef_discount frozen key {key!r} looks like a misspelling of "
                f"{CEF_SIZING_KEY!r}; the sleeve would ignore it and size the book at 1.0. "
                f"Spell it {CEF_SIZING_KEY!r}, or delete it (absent is today's book)")
    if CEF_SIZING_KEY not in frozen or frozen[CEF_SIZING_KEY] is None:
        return None
    v = frozen[CEF_SIZING_KEY]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"cef_discount {CEF_SIZING_KEY} must be a number, got {v!r} "
                         f"({type(v).__name__})")
    import math
    if not math.isfinite(float(v)) or not float(v) > 0.0:
        raise ValueError(f"cef_discount {CEF_SIZING_KEY} {v!r} must be a finite number above 0 "
                         f"(a multiple of the unit book; 1.0 is today's size)")
    return float(v)


# ---------------------------------------------------------------------------
# level_signal (CEF trial 54, results/cef/PREREG_C4_LEVEL_2026-11-02.md)
# ---------------------------------------------------------------------------

CEF_LEVEL_KEY = "level_signal"
CEF_LEVEL_FIELDS = ("risk_share", "family_of")


def cef_level_signal(frozen):
    """`level_signal` parsed to {"risk_share": float, "family_of": {ticker: family}}, or None
    when ABSENT (today's book: the z target alone).

    WHAT IT IS. A second, within-family DISCOUNT-LEVEL target blended with the z target at
    equal ex-ante risk (PREREG_C4_LEVEL §1.2; what the sleeve does is in
    src/deploy/sleeves/cef_discount.py, `_level_weights` and `_blend_unit_book`). The z is
    standardised against each fund's own 252-session history, so a fund that has sat 10pp rich
    of its family for a year has z near zero; the level sees it (§2).

    `risk_share` IS THE SHARE OF EX-ANTE RISK ON THE Z BOOK, the level book taking
    1 - risk_share: mix = risk_share * w_z / s_z + (1 - risk_share) * w_L / s_L. That is the
    quantity §3.1 derives ("0.514 on z", rounded to 0.50) and its plateau table varies ("share
    of risk on z"). §1.3 test 2 reads "risk_share 0 (all risk on z)", the other way round; at
    the pre-registered 0.50 the two readings are the same book, and the spec's note says which
    one this code is. UNITS: a fraction of risk, not of gross and not a percent.

    REFUSED, naming the value (no silent defaults):
      * null, or anything but an object with exactly the keys {risk_share, family_of}. A null
        here would read as "off" beside a note that describes it as on; the REVERT is to
        delete the key, so there is no second spelling of absent;
      * risk_share a bool, a non-number, NaN or inf, or outside the OPEN interval (0, 1). At 0
        or 1 one book has no risk and its weights only add noise to the arithmetic; the
        z-only book is the key ABSENT, and an all-level book is a different trial;
      * family_of not an object of non-empty ticker -> non-empty family strings, or not
        covering the universe EXACTLY. A universe name with no family would raise on the first
        day it became eligible (a missed day, found late); a family for a name outside the
        universe says the map and the universe were copied from different files. Both are
        refused here, naming the tickers, at load and at the sleeve's construction;
      * `band_width` absent or null beside it. The trial measures the daily level through the
        band (§3.2); without a band the signal date can sit before the last panel date (the
        `rebalance_days` calendar), and the blend's vols would then read returns past the date
        its weights were formed on. That construction was never measured;
      * a frozen key that looks like a misspelling of it (`cef_c4_near_miss`'s rule). Absent
        is today's book, so a misspelt key would trade the z book while the spec reads as
        blended.
    """
    note = f"_{CEF_LEVEL_KEY}_note"
    for key in frozen:
        if not isinstance(key, str) or key in (CEF_LEVEL_KEY, note):
            continue
        stem = key.strip().lower().replace("-", "_").replace(" ", "_").strip("_")
        if stem.endswith("_note"):
            stem = stem[:-len("_note")].strip("_")
        if (stem == CEF_LEVEL_KEY or stem.replace("_", "") == CEF_LEVEL_KEY.replace("_", "")
                or _osa_distance(stem, CEF_LEVEL_KEY) <= CEF_C4_NEAR):
            raise ValueError(
                f"cef_discount frozen key {key!r} looks like a misspelling of {CEF_LEVEL_KEY!r}; "
                f"the sleeve would ignore it and trade the z book alone. Spell it "
                f"{CEF_LEVEL_KEY!r}, or delete it (absent is today's book)")
    if CEF_LEVEL_KEY not in frozen:
        return None
    v = frozen[CEF_LEVEL_KEY]
    if not isinstance(v, dict) or set(v) != set(CEF_LEVEL_FIELDS):
        got = f"keys {sorted(map(str, v))}" if isinstance(v, dict) else f"{v!r} ({type(v).__name__})"
        raise ValueError(f"cef_discount {CEF_LEVEL_KEY} must be an object with exactly the keys "
                         f"{list(CEF_LEVEL_FIELDS)}, got {got}")
    rs = v["risk_share"]
    if isinstance(rs, bool) or not isinstance(rs, (int, float)):
        raise ValueError(f"cef_discount {CEF_LEVEL_KEY}.risk_share must be a number, got {rs!r} "
                         f"({type(rs).__name__})")
    import math
    if not math.isfinite(float(rs)) or not 0.0 < float(rs) < 1.0:
        raise ValueError(f"cef_discount {CEF_LEVEL_KEY}.risk_share {rs!r} must be strictly between "
                         f"0 and 1 (the share of ex-ante risk on the z book; the z book alone is "
                         f"the key absent)")
    fam = v["family_of"]
    if not isinstance(fam, dict) or not fam:
        raise ValueError(f"cef_discount {CEF_LEVEL_KEY}.family_of must be a non-empty object "
                         f"{{ticker: family}}, got {type(fam).__name__}")
    bad = sorted(repr(k) for k, g in fam.items()
                 if not (isinstance(k, str) and k and isinstance(g, str) and g.strip()))
    if bad:
        raise ValueError(f"cef_discount {CEF_LEVEL_KEY}.family_of must map non-empty ticker "
                         f"strings to non-empty family strings; bad entries for {bad}")
    uni = frozen.get("universe")
    if not isinstance(uni, list):
        raise ValueError(f"cef_discount {CEF_LEVEL_KEY} is set but the frozen universe is "
                         f"{uni!r}; family_of is checked against it")
    missing = sorted(set(uni) - set(fam))
    if missing:
        raise ValueError(f"cef_discount {CEF_LEVEL_KEY}.family_of has no family for {missing}; "
                         f"every universe name needs one (refusing to guess a family)")
    stray = sorted(set(fam) - set(uni))
    if stray:
        raise ValueError(f"cef_discount {CEF_LEVEL_KEY}.family_of names {stray}, which are not "
                         f"in the frozen universe")
    if frozen.get("band_width") in (None, ""):
        raise ValueError(f"cef_discount {CEF_LEVEL_KEY} is set but band_width is not; the level "
                         f"blend is defined on the daily signal through the band (PREREG_C4_LEVEL "
                         f"§3.2), never on the rebalance_days calendar")
    return {"risk_share": float(rs), "family_of": {str(k): str(g) for k, g in fam.items()}}


def _validate_cef_discount(spec):
    """The CEF sleeve's whole signal is price minus NAV, so the things that can
    silently break it are a missing universe, a NAV staleness tolerance wide
    enough to trade blind, and an unbounded volatility scalar. The four
    optional C4 keys (above) are parsed here too, so a malformed one refuses
    the spec at load rather than at the first decide, and so is `level_signal`
    (CEF trial 54), whose family map is checked against the universe here."""
    f = _require_dict(spec, "frozen")
    cef_optional_keys(f)
    cef_below_min_names_floor(f)
    cef_thin_stop_levels(spec)      # CEF trial 55's K1-K3 report lines (risk block); absent: nothing
    cef_level_signal(f)
    uni = f.get("universe")
    if not isinstance(uni, list) or len(uni) < 6:
        raise ValueError("cef_discount needs a frozen universe of >= 6 funds; "
                         "the book is cross-sectional and cannot be formed from fewer")
    vt = float(f.get("vol_target_annual", 0.0))
    if not 0.005 <= vt <= 0.40:
        raise ValueError(f"vol_target_annual {vt} outside a sane 0.5%-40% band")
    m = cef_sizing_multiplier(f)
    if m is not None:
        # A multiplier with no cap would lever the account past Reg T with nothing in the
        # sleeve to stop it, and the effective target is the one the sane band guards.
        if f.get("max_gross_stress") in (None, ""):
            raise ValueError(
                f"cef_discount {CEF_SIZING_KEY} {m} is set but max_gross_stress is not; the "
                f"multiplier is held under the account's own gross cap and there is none")
        if not 0.005 <= vt * m <= 0.40:
            raise ValueError(
                f"cef_discount {CEF_SIZING_KEY} {m} x vol_target_annual {vt} = {vt * m:.4f} is "
                f"outside the sane 0.5%-40% band for the account's effective vol target")
    age = int(f.get("max_nav_age_bd", 3))
    if not 1 <= age <= 5:
        raise ValueError(
            f"max_nav_age_bd {age} outside 1-5. A fund whose NAV has not "
            "updated is not a cheap fund, it is a blind one.")
    if float(f.get("min_adv_usd", 0.0)) < 1.0e6:
        raise ValueError("min_adv_usd below $1m; CEFs are thin and this book "
                         "cannot assume it can trade names that do not trade")


_TYPE_VALIDATORS = {
    CEF_DISCOUNT_ALLOC_TYPE: _validate_cef_discount,
    "static_weights": _validate_static_weights,
}


def validate_spec(spec) -> None:
    """Structural accept/reject for any allowed alloc type. Raises ValueError on
    a malformed spec; returns None on accept."""
    t = _validate_common(spec)
    _TYPE_VALIDATORS[t](spec)



# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def build_sleeve(spec, capital_usd, **sleeve_kw):
    """Instantiate the Sleeve for this spec. Validates first. The import is
    not wrapped: a sleeve module that fails to import must fail loudly here,
    not degrade into a misleading "not implemented" message.

    `sleeve_kw` (added 2026-11-03, CEF trial 55) is passed to the sleeve's
    constructor unchanged, and nothing here reads it. It exists for the
    `cef_discount` sleeve's `account` declaration: `below_min_names =
    "trade_eligible"` is PAPER ONLY, and the sleeve refuses to decide under it
    unless its caller declared the account paper at construction
    (PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md §1.2). With none given the call is
    the one before the argument existed, so every caller that passes nothing
    builds exactly what it built before. A sleeve that does not take a keyword
    raises TypeError, naming it: a declaration silently dropped would be no
    declaration."""
    validate_spec(spec)
    t = spec["allocation"]["type"]
    from . import sleeves  # noqa: F401  (imports register the built sleeves)
    cls = _REGISTRY.get(t)
    if cls is None:
        raise NotImplementedError(
            f"allocation type {t!r} validates but no sleeve class registers "
            f"under it. Registered: {sorted(_REGISTRY)}.")
    return cls(spec, capital_usd, **sleeve_kw)
