"""Second method for the third rule's targets: ask the LIVE SLEEVE to build them (report only).

`band_frontier.build_targets(min_names=f)` claims to build, on a session with
f <= n < min_names eligible names, the target the live sleeve would build on
those n names. This script does not re-implement the construction. It calls
`CEFDiscountSleeve.target_positions` on EVERY thin session of the spec (fewer
than the spec's `min_names` eligible: 3,622 sessions on the panel of
2026-10-15), with a DEEP COPY of the live frozen spec, read through
`scripts/cef/spec.py`, in which only `min_names` is lowered to 3, the lowest
floor the report scores. Nothing is written to `ops/specs/`: the copy lives in
this process. Each call has a flat book, `sleeve_nav` = 1.0, no holds and
`opening_session` = True, so the band is skipped (cef_discount.py l.1050) and
the sleeve emits its full target after the min-weight block (l.926-933), the
group cap (off in v7) and the gross ceiling (l.1113-1116). Its answer is
compared, in `third_rule.py`, with `_cap_gross(build_targets(min_names=3) row,
max_gross_stress)`.

One construction detail differs by design and is reported, not hidden: the
sleeve's min-weight re-neutralisation runs only when at least `min_names`
names survive the 0.005 filter (l.928), and here that is the patched 3. The
harness models no `min_abs_weight` for any rule (PR #33, "Not modelled"). A
session on which some eligible weight is under 0.005 is flagged in the CSV so
the comparison can say how many there were.

One target is the same at floor 3, 4 and 5 on a session with n >= 5 eligible
(the construction does not read the floor), so one run covers all three
floors; at n = 3 or 4 only the floors at or below n trade.

The sleeve decides on `data/cef/` truncated at asof (`_read_panel`), so each
call is the decision as it would have been made that evening. pandas' parquet
reader is memoised IN THIS PROCESS ONLY (as in PR #33's sleeve_thin_check.py)
and hands each call its own copy.

    python3 results/backtests/thin-third-rule-2026-11-03/sleeve_reduced_check.py   # about 5 min

Writes sleeve_reduced.csv beside this file: date, status ("below" = every name
FLAT "cef: only N eligible names"; "traded" otherwise), n_below (N when
below), minw_reason (the names the sleeve returned FLAT with the reason "below
min weight"), and the sleeve's signed weight for each universe name (0 for
FLAT). minw_reason is NOT a count of min-weight events: the sleeve gives that
reason both to an eligible name under `min_abs_weight` and to a name that never
had a z-score (l.1196, `dict(dropped).get(tk, "below min weight")`; only masked
names enter `dropped` without a z), so third_rule.py identifies the eligible
names under the threshold from the targets themselves and does not read it.
"""
import copy
import functools
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]          # the worktree root
sys.path.insert(0, str(REPO))

import pandas as pd                                   # noqa: E402

_read = pd.read_parquet


@functools.lru_cache(maxsize=None)
def _cached(path, columns):
    return _read(path, columns=list(columns) if columns else None)


def _memo(path, columns=None, **kw):
    if kw:
        raise TypeError(f"unexpected read_parquet kwargs {kw}")
    return _cached(str(path), tuple(columns) if columns else None).copy()


pd.read_parquet = _memo                               # this process only

from scripts.cef import band_frontier as bf           # noqa: E402
from scripts.cef.spec import SPEC_ID, UNIVERSE, spec  # noqa: E402
from src.deploy.sleeve import FLAT, MarketState       # noqa: E402
from src.deploy.sleeves.cef_discount import CEFDiscountSleeve   # noqa: E402

THIN = re.compile(r"^cef: only (\d+) eligible names$")
FLOOR = 3          # the lowest floor scored; see the module docstring


def main():
    T, _ = bf.build_targets()
    thin = bf.thin_sessions(T.index)
    sp = copy.deepcopy(spec())
    live_min = int(sp["frozen"]["min_names"])
    sp["frozen"]["min_names"] = FLOOR                 # in memory only; ops/specs/ is not touched
    sl = CEFDiscountSleeve(sp, 1.0)
    rows = []
    dates = T.index[thin.to_numpy()]
    for i, d in enumerate(dates):
        ms = MarketState(asof=d, prices=pd.DataFrame(), holdings={},
                         extras={"sleeve_nav": 1.0, "opening_session": True})
        out = sl.target_positions(d, ms)
        m = [THIN.match(t.reason) for t in out]
        below = all(x is not None for x in m) and all(t.side == FLAT for t in out)
        if any(x is not None for x in m) and not below:
            raise AssertionError(f"{d.date()}: a partial 'only N eligible' answer")
        early = {t.reason for t in out} & {"cef: insufficient history", "cef: no price/NAV panel",
                                          "cef: band on but sleeve NAV unknown"}
        if early:
            raise AssertionError(f"{d.date()}: the sleeve returned {sorted(early)}; not a decision")
        if any(t.qty is not None for t in out):
            raise AssertionError(f"{d.date()}: a qty target from a flat book; the opening path was not taken")
        w = {t.instrument: (0.0 if t.side == FLAT else float(t.weight)) for t in out}
        minw = sorted(t.instrument for t in out if t.side == FLAT and "below min weight" in t.reason)
        rows.append(dict(date=d.date().isoformat(), status="below" if below else "traded",
                         n_below=int(m[0].group(1)) if below else -1, minw_reason=";".join(minw),
                         **{tk: w[tk] for tk in UNIVERSE}))
        if i % 500 == 0:
            print(i, d.date(), rows[-1]["status"], flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(HERE / "sleeve_reduced.csv", index=False, float_format="%.17g")
    print(SPEC_ID, f"(min_names {live_min} -> {FLOOR} in memory)", "thin dates", len(df),
          "below", int((df.status == "below").sum()), "traded", int((df.status == "traded").sum()))


if __name__ == "__main__":
    main()
