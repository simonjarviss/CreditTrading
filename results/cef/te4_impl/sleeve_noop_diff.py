"""The no-op proof for CEF trial 55's sleeve code (te4): the core sleeve, key absent, byte for byte.

WHY (CLAUDE.md, code rules: "a new frozen-spec key must default to current behaviour, and the
no-op must be proved by diffing sleeve output byte-for-byte with the key absent"; the
pre-registration results/cef/PREREG_THIN_TRADE_ELIGIBLE_2026-11-03.md §1.6). The te4 commits
add `below_min_names = "trade_eligible"`, `below_min_names_floor`, an `account` declaration on
the sleeve's constructor and a reduced branch in `target_positions`. None of it may move a single
byte of the core's targets while the spec does not set the key, and none of it may move them when
the key is written out as its default, "flatten".

WHAT IT DOES. Runs `CEFDiscountSleeve.target_positions` from TWO checkouts of this repository --
the code before te4 (`--base-tree`, a worktree at ac15d09) and the code under test (`--new-tree`,
default: the checkout this file is in) -- each in its own fresh interpreter, with:

  * the LIVE spec, read through that checkout's `scripts/cef/spec.py` (the two spec files must be
    byte-identical; checked), never edited: the variants below are copies in memory;
  * the SAME real panel for both: `data/cef/` of the new tree, read only (the sleeve's PX_PATH and
    NAV_PATH are pointed at it in each child, because a fresh worktree has no `data/`);
  * every decision date of the panel: every date on which the universe has a paired close and NAV
    above $0.50, the sleeve's own inner join (`_read_panel`), from the first to the last;
  * two books on each date: FLAT (holdings {}, `opening_session` False: the band trades from zero
    to the edge, the path a re-entry after a flat day takes) and HELD (a fixed share book, every
    universe name, alternating +700 / -500 shares, so the band's HOLD and TRADE branches, the
    dust filter and the gross ceiling all run); `sleeve_nav` = the spec's `capital_usd`.

Variants (a child each):
  base:absent     ac15d09's code, the live spec              -- the reference
  base:flatten    ac15d09's code, below_min_names "flatten"   -- the default written out, before
  base:hold       ac15d09's code, below_min_names "hold"      -- the reference for "hold"
  new:absent      the new code, the live spec                 -- must equal base:absent
  new:flatten     the new code, below_min_names "flatten"     -- must equal base:absent
  new:hold        the new code, below_min_names "hold"        -- must equal base:hold
  new:te4         the new code, below_min_names "trade_eligible", floor (below), account "paper",
                  extras thin_rule {"stop": None}: on every date with at least `min_names`
                  eligible names its targets, with meta["cef_thin"] removed, must equal
                  base:absent (§1.6 item 2); the thin dates are counted, not compared, because
                  there the rule is meant to differ.

WHY "hold" IS COMPARED WITH base:hold, NOT base:absent (added after the reviews of f1d9f62).
The sleeve's module docstring says the targets under ABSENT, "flatten" or "hold" are today's,
byte for byte, and cites this script; as first written the script ran no "hold" child, so that
third claim cited evidence the repository did not contain. "hold" is a different rule from
"flatten" by design (it holds the book, and it sets `strict`, so a panel too short to score
RAISES instead of flattening), so the claim is that te4's code did not change what "hold" does:
new:hold against ac15d09's own "hold". The raises are compared like target lists; both children
read the same `data/cef/`, so a message that names a panel path names the same one. `COMPARE`
below is the table of claims the verdict checks; src/deploy/tests/ pins that it covers every rule
the sleeve's docstring names.

EVERY CHILD RUNS WITH PYTHONHASHSEED=0. The band iterates `set(w.index) | set(held_w)`, so the
order in which the banded book is summed for the gross ceiling follows the string hash seed, and
two runs of the SAME code under different seeds differ in the last bit of a capped weight.
Measured 2026-11-03 with this script's child on the last 150 decision dates (new:absent): seeds 1,
2 and 3 against seed 0 differed on 23, 24 and 20 of the 300 (date, book) lists, each by one or two
ulps in a weight (0.3115173064058714 against 0.31151730640587133). A fixed seed makes the children
comparable; it moves nothing but that summation order. (That the live sleeve is reproducible only
to the last bit across processes is a finding about today's code, reported, not changed here.)

Each target is reduced to (instrument, side, kind, qty, weight, reason, combo_id, meta items in
order), the list for one (date, book) is pickled (protocol 4), and the pickles are hashed: sha256
per (date, book), and sha256 of the concatenation in date order per variant. A raise on a date is
recorded as ("RAISE", type, message) and compared like a target list. The comparison is of those
bytes: equal hashes mean equal pickles, which mean equal floats bit for bit, equal reasons
character for character and equal meta.

THE FLOOR for new:te4 is read from the spec (`scripts/cef/spec.py`'s BELOW_MIN_NAMES_FLOOR) once
the key exists; until the activation commit sets it, the pre-registration's approved value, 4
(§1.1, derived there, not here), as `results/cef/prereg_thin_te4/compose.py` does. The output says
which.

    python3 results/cef/te4_impl/sleeve_noop_diff.py --base-tree <worktree at ac15d09>
    # seven children in parallel, each about 21 minutes on every date (measured 2026-11-03
    # with five: 1,278-1,293 s per child, 7,018 dates); --dates last:200 for a quick look

Writes `sleeve_noop_diff_output_<stamp>.txt` beside this file (never overwriting another stamp's
without --overwrite), and the per-variant pickles under --workdir (a temporary directory unless
given). Read only: it opens the panels and the spec, and writes nothing under data/ or ops/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import functools
import hashlib
import json
import os
import pickle
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEW_TREE = HERE.parents[2]
VARIANTS = ("base:absent", "base:flatten", "base:hold", "new:absent", "new:flatten", "new:hold",
            "new:te4")
# Each claim the verdict checks: variant -> the variant it must equal byte for byte, every
# (date, book). new:te4 is checked separately (full sessions only, meta["cef_thin"] removed).
COMPARE = {"base:flatten": "base:absent", "new:absent": "base:absent",
           "new:flatten": "base:absent", "new:hold": "base:hold"}
PREREG_FLOOR = 4          # §1.1 of the pre-registration; used only until the spec carries the key
HELD_LONG, HELD_SHORT = 700.0, -500.0


# ---------------------------------------------------------------------------
# the child: one checkout, one variant
# ---------------------------------------------------------------------------

def _canon(targets):
    return [(t.instrument, t.side, t.kind, t.qty, t.weight, t.reason, t.combo_id,
             tuple(t.meta.items())) for t in targets]


def child(tree: Path, variant: str, data: Path, dates_file: Path, out: Path) -> None:
    sys.path.insert(0, str(tree))
    import copy

    import pandas as pd

    _read = pd.read_parquet

    @functools.lru_cache(maxsize=None)
    def _cached(path, columns):
        return _read(path, columns=list(columns) if columns else None)

    def _memo(path, columns=None, **kw):
        if kw:
            raise TypeError(f"unexpected read_parquet kwargs {kw}")
        return _cached(str(path), tuple(columns) if columns else None).copy()

    pd.read_parquet = _memo                   # this process only: the same frames, read once

    from scripts.cef import spec as S
    from src.deploy.sleeve import MarketState
    from src.deploy.sleeves import cef_discount as cefmod

    loaded = Path(cefmod.__file__).resolve()
    if tree.resolve() not in loaded.parents:
        raise AssertionError(f"{variant}: imported the sleeve from {loaded}, not from {tree}")
    cefmod.PX_PATH = data / "cef_prices.parquet"
    cefmod.NAV_PATH = data / "cef_nav.parquet"
    cefmod.GRP_PATH = cefmod.PX_PATH

    sp = copy.deepcopy(S.spec())
    fr = sp["frozen"]
    if "below_min_names" in fr or "below_min_names_floor" in fr:
        raise AssertionError("the live spec sets below_min_names; this proof is of the key ABSENT")
    kw, extras_add, floor_note = {}, {}, ""
    rule = variant.split(":")[1]
    if rule in ("flatten", "hold"):
        fr["below_min_names"] = rule
    elif rule == "te4":
        floor = getattr(S, "BELOW_MIN_NAMES_FLOOR", None)
        floor_note = ("the spec's below_min_names_floor" if floor is not None
                      else f"the pre-registration's approved {PREREG_FLOOR} (not yet a spec key)")
        fr["below_min_names"] = "trade_eligible"
        fr["below_min_names_floor"] = int(floor) if floor is not None else PREREG_FLOOR
        kw = {"account": "paper"}
        extras_add = {"thin_rule": {"stop": None}}
    elif rule != "absent":
        raise ValueError(variant)
    sl = cefmod.CEFDiscountSleeve(sp, float(sp["capital_usd"]), **kw)
    nav = float(sp["capital_usd"])
    uni = sl.instruments()
    held = {t: (HELD_LONG if i % 2 == 0 else HELD_SHORT) for i, t in enumerate(uni)}
    dates = [pd.Timestamp(d) for d in json.loads(dates_file.read_text())]
    books = {"flat": {}, "held": held}
    rec = {}
    t0 = time.time()
    for d in dates:
        for name, holdings in books.items():
            ms = MarketState(asof=d, prices=pd.DataFrame(), holdings=dict(holdings),
                             extras={"sleeve_nav": nav, "opening_session": False, **extras_add})
            try:
                got = _canon(sl.target_positions(d, ms))
            except Exception as exc:            # noqa: BLE001 -- recorded and compared, not hidden
                got = ("RAISE", type(exc).__name__, str(exc))
            rec[(d.date().isoformat(), name)] = got
    blob = {k: pickle.dumps(v, protocol=4) for k, v in rec.items()}
    out.write_bytes(pickle.dumps({"variant": variant, "tree": str(tree), "spec_id": S.SPEC_ID,
                                  "floor_note": floor_note, "seconds": time.time() - t0,
                                  "blob": blob}, protocol=4))


# ---------------------------------------------------------------------------
# the driver
# ---------------------------------------------------------------------------

def _git(tree: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(tree), *args], check=True, capture_output=True,
                          text=True).stdout.strip()


def _blob(tree: Path, rel: str) -> str:
    """The git blob id of a file's CURRENT content (committed or not): `git ls-tree <commit>
    <rel>` shows the same id for the commit that holds this content."""
    return _git(tree, "hash-object", rel)


def _decision_dates(new_tree: Path, data: Path, sel: str) -> list:
    sys.path.insert(0, str(new_tree))
    import pandas as pd
    from scripts.cef.spec import UNIVERSE
    P = pd.read_parquet(data / "cef_prices.parquet", columns=["date", "ticker", "close"])
    N = pd.read_parquet(data / "cef_nav.parquet", columns=["date", "ticker", "nav"])
    P, N = P[P.ticker.isin(UNIVERSE)], N[N.ticker.isin(UNIVERSE)]
    d = P.merge(N, on=["date", "ticker"], how="inner")
    d = d[(d.nav > 0.5) & (d.close > 0.5)]
    dates = sorted(pd.to_datetime(d["date"]).unique())
    if sel == "all":
        pass
    elif sel.startswith("last:"):
        dates = dates[-int(sel.split(":")[1]):]
    else:
        raise ValueError(f"--dates {sel!r}: 'all' or 'last:N'")
    return [pd.Timestamp(x).date().isoformat() for x in dates]


def _variant_hash(blob: dict, keys: list) -> str:
    h = hashlib.sha256()
    for k in keys:
        h.update(blob[k])
    return h.hexdigest()


def _strip_thin(canon):
    if canon and canon[0] == "RAISE":
        return canon
    return [(*t[:7], tuple((k, v) for k, v in t[7] if k != "cef_thin")) for t in canon]


def driver(a) -> int:
    base, new = Path(a.base_tree).resolve(), Path(a.new_tree).resolve()
    data = (new / "data" / "cef").resolve()
    for p in (base, new, data / "cef_prices.parquet", data / "cef_nav.parquet"):
        if not p.exists():
            raise FileNotFoundError(f"{p} does not exist")
    spec_rel = "ops/specs/cef_discount.frozen.json"
    if (base / spec_rel).read_bytes() != (new / spec_rel).read_bytes():
        raise AssertionError(f"{spec_rel} differs between the two trees; the proof needs one spec")
    stamp = a.stamp or dt.date.today().isoformat()
    out_txt = HERE / f"sleeve_noop_diff_output_{stamp}.txt"
    if out_txt.exists() and not a.overwrite:
        raise FileExistsError(f"{out_txt} exists; pass --overwrite or another --stamp")
    work = Path(a.workdir) if a.workdir else Path(tempfile.mkdtemp(prefix="te4_noop_"))
    work.mkdir(parents=True, exist_ok=True)
    dates = _decision_dates(new, data, a.dates)
    # The record of WHAT is tested is taken now, before any child starts: an edit made in the
    # checkout while the children run cannot change it (the children import at start-up).
    head = [f"base: a worktree at {_git(base, 'rev-parse', 'HEAD')}"]
    dirty = _git(new, "status", "--porcelain", "--untracked-files=no")
    head.append(f"new:  this checkout at {_git(new, 'rev-parse', 'HEAD')}"
                + (" + uncommitted changes to tracked files" if dirty else " (clean)"))
    for rel in ("src/deploy/sleeves/cef_discount.py", "src/deploy/registry.py",
                "src/deploy/sleeve.py"):
        head.append(f"  code under test, git blob ids: {rel}  base {_blob(base, rel)[:12]}  "
                    f"new {_blob(new, rel)[:12]}")
    import pandas as pd
    pdates = pd.read_parquet(data / "cef_prices.parquet", columns=["date"])["date"]
    ndates = pd.read_parquet(data / "cef_nav.parquet", columns=["date"])["date"]
    panel_note = (f"panel data/cef/, prices to {pd.Timestamp(pdates.max()).date()}, "
                  f"NAV to {pd.Timestamp(ndates.max()).date()}")
    dates_file = work / "dates.json"
    dates_file.write_text(json.dumps(dates))
    procs = {}
    for v in VARIANTS:
        tree = base if v.startswith("base") else new
        out = work / f"{v.replace(':', '_')}.pkl"
        procs[v] = (subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--child",
                                      "--tree", str(tree), "--variant", v, "--data", str(data),
                                      "--dates-file", str(dates_file), "--out", str(out)],
                                     cwd=str(tree), env={**os.environ, "PYTHONHASHSEED": "0"}),
                    out)
    for v, (p, _) in procs.items():
        if p.wait() != 0:
            raise RuntimeError(f"child {v} exited {p.returncode}")
    R = {v: pickle.loads(out.read_bytes()) for v, (_, out) in procs.items()}
    keys = [(d, b) for d in dates for b in ("flat", "held")]
    for v in VARIANTS:
        if set(R[v]["blob"]) != set(keys):
            raise AssertionError(f"{v} did not record every (date, book)")
    lines = []
    P = lines.append
    P(f"te4 sleeve no-op proof, {stamp} (python3 results/cef/te4_impl/sleeve_noop_diff.py)")
    for h in head:
        P(h)
    P(f"spec {R['base:absent']['spec_id']} (identical file in both trees); {panel_note}")
    P(f"decision dates: {len(dates)} ({dates[0]} .. {dates[-1]}, --dates {a.dates}); "
      f"books flat and held; {len(keys)} (date, book) target lists per variant")
    P(f"new:te4 floor: {R['new:te4']['floor_note']}")
    P("")
    ref = R["base:absent"]["blob"]
    for v in VARIANTS:
        b = R[v]["blob"]
        raises = sum(1 for k in keys if pickle.loads(b[k])[:1] == ("RAISE",))
        P(f"  {v:<13} sha256 {_variant_hash(b, keys)}   raises {raises:>5}   "
          f"{R[v]['seconds']:.0f}s")
    P("")
    ok = True
    for v, against in COMPARE.items():
        want = R[against]["blob"]
        diff = [k for k in keys if R[v]["blob"][k] != want[k]]
        # A byte difference with equal reprs would be pickle's memo (shared objects), not a value;
        # it is reported separately and still fails the verdict.
        vals = [k for k in diff
                if repr(pickle.loads(R[v]["blob"][k])) != repr(pickle.loads(want[k]))]
        ok &= not diff
        P(f"{v:<13} vs {against}: {len(keys) - len(diff)} of {len(keys)} (date, book) pickles "
          f"byte-identical" + (f"; {len(diff)} differ in bytes, {len(vals)} in value; FIRST "
                               f"{diff[0]}" if diff else ""))
    # te4: equal to the reference wherever at least min_names were eligible (meta["cef_thin"]
    # removed); the thin dates are counted by what the rule did.
    te4 = R["new:te4"]["blob"]
    full = thin = red = below = held_thin = differ = red_moved = 0
    first = None
    for k in keys:
        got = pickle.loads(te4[k])
        if got[:1] == ("RAISE",):
            if pickle.loads(ref[k]) != got:
                differ += 1
                first = first or (k, "raise")
            continue
        info = [dict(t[7]).get("cef_thin") for t in got]
        if any(i is None for i in info) or any(i != info[0] for i in info):
            raise AssertionError(f"{k}: a te4 target without one shared meta['cef_thin']")
        i0 = info[0]
        # repr, not pickle bytes: the stripped list is rebuilt here, so its pickle memo need not
        # match the reference's; repr of a float is exact (it round-trips), so this is bit-level.
        same = repr(_strip_thin(got)) == repr(pickle.loads(ref[k]))
        if i0["n"] >= i0["min_names"]:
            full += 1
            if not same:
                differ += 1
                first = first or (k, "full")
        else:
            thin += 1
            red += bool(i0["reduced"])
            below += i0["n"] < i0["floor"]
            held_thin += bool(i0["holds"])
            red_moved += bool(i0["reduced"]) and not same
    ok &= differ == 0
    P(f"new:te4       vs base:absent on (date, book) with >= min_names eligible: "
      f"{full - differ} of {full} byte-identical with meta['cef_thin'] removed"
      + (f"; FIRST DIFFERENCE {first}" if differ else ""))
    P(f"              thin (date, book): {thin}; reduced build ran on {red}; below the floor "
      f"(FLAT) {below}; with holds {held_thin}")
    P(f"              sensitivity: the reduced build's targets differ from base:absent's FLAT on "
      f"{red_moved} of {red} (the comparison can see a change)")
    P("")
    P("VERDICT: " + ("NO-OP PROVED (every comparison byte-identical)" if ok else "DIFFERENCES FOUND"))
    text = "\n".join(lines) + "\n"
    out_txt.write_text(text)
    print(text, end="")
    print(f"pickles in {work}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base-tree")
    ap.add_argument("--new-tree", default=str(NEW_TREE))
    ap.add_argument("--dates", default="all")
    ap.add_argument("--workdir")
    ap.add_argument("--stamp")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--child", action="store_true")
    ap.add_argument("--tree")
    ap.add_argument("--variant", choices=VARIANTS)
    ap.add_argument("--data")
    ap.add_argument("--dates-file")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.child:
        child(Path(a.tree).resolve(), a.variant, Path(a.data), Path(a.dates_file), Path(a.out))
        return 0
    if not a.base_tree:
        ap.error("--base-tree (a worktree at the code before te4) is required")
    return driver(a)


if __name__ == "__main__":
    sys.exit(main())
