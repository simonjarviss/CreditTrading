"""Second method for the thin-session set: ask the LIVE SLEEVE itself (report only).

`band_frontier.thin_sessions` counts a name eligible on decision date t when it
has a finite z-score and an ADV at or above the spec's floor. The live sleeve
(`src/deploy/sleeves/cef_discount.py::target_positions`) applies more tests:
z finite (l.809), ADV measured (l.824), ADV >= floor (l.826), a NAV row
(l.830), NAV age <= `max_nav_age_bd` (l.832-834) and the runner's stale-NAV
holds (l.837; runtime only, `extras["nav_hold"]`, which no historical date
has). This script does not re-implement any of them. It calls
`CEFDiscountSleeve.target_positions` on EVERY decision date of the harness's
target index, with the live frozen spec read through `scripts/cef/spec.py`, a
flat book, `sleeve_nav` = 1.0 and no holds, and reads the answer off the
sleeve's own reason strings:

  * a thin session is one where EVERY target is FLAT with the reason
    "cef: only N eligible names" (the flatten branch, l.892-895), and N is the
    sleeve's own count of eligible names;
  * any reason containing "stale" or "no NAV" means the NAV tests dropped a name
    that the harness would have counted (only visible on non-thin dates, where
    dropped names come back FLAT with their reason, l.1195-1198).

The sleeve decides on `data/cef/` truncated at asof (`_read_panel`, l.627), so
each call is the decision as it would have been made that evening. Nothing is
written to data/; pandas' parquet reader is memoised IN THIS PROCESS ONLY so
5,480 calls take minutes, and the memo hands each call its own copy.

    python3 results/backtests/thin-days-2026-11-03/sleeve_thin_check.py

Writes results/backtests/thin-days-2026-11-03/sleeve_thin.csv (date, thin, n_eligible,
nav_drop_names). Read by thin_days.py, which compares it with thin_sessions().
"""
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
from scripts.cef.spec import SPEC_ID, spec            # noqa: E402
from src.deploy.sleeve import FLAT, MarketState       # noqa: E402
from src.deploy.sleeves.cef_discount import CEFDiscountSleeve   # noqa: E402

THIN = re.compile(r"^cef: only (\d+) eligible names$")


def main():
    T, _ = bf.build_targets()
    sl = CEFDiscountSleeve(spec(), 1.0)
    rows = []
    for i, d in enumerate(T.index):
        ms = MarketState(asof=d, prices=pd.DataFrame(), holdings={}, extras={"sleeve_nav": 1.0})
        out = sl.target_positions(d, ms)
        m = [THIN.match(t.reason) for t in out]
        thin = all(x is not None for x in m) and all(t.side == FLAT for t in out)
        if any(x is not None for x in m) and not thin:
            raise AssertionError(f"{d.date()}: a partial 'only N eligible' answer; the sleeve's "
                                 f"flatten branch was not read correctly")
        n = int(m[0].group(1)) if thin else -1
        early = {t.reason for t in out} & {"cef: insufficient history", "cef: no price/NAV panel",
                                          "cef: band on but sleeve NAV unknown"}
        if early:
            raise AssertionError(f"{d.date()}: the sleeve returned {sorted(early)}; not a decision")
        navdrop = sorted(t.instrument for t in out if ("stale" in t.reason or "no NAV" in t.reason))
        rows.append((d.date().isoformat(), thin, n, ";".join(navdrop)))
        if i % 500 == 0:
            print(i, d.date(), thin, n, flush=True)
    df = pd.DataFrame(rows, columns=["date", "thin", "n_eligible", "nav_drop_names"])
    df.to_csv(HERE / "sleeve_thin.csv", index=False)
    print(SPEC_ID, "dates", len(df), "thin", int(df.thin.sum()),
          "dates with a NAV drop", int((df.nav_drop_names != "").sum()))


if __name__ == "__main__":
    main()
