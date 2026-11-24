"""S6 -- M6 corporate events on THIS book's own names: how many are there? Zero trials, counts only.

The question for this set-up is not whether CEF events pay (the EVENTS lane owns
that: NAV tenders KILLED D2, E1 in Stage 0, A1 and A2 closed), but whether the
87 names the two accounts trade see enough dated events for an overlay or a
subtract-only guard to matter. It reads the EDGAR census the events lane built
(results/events/cef_corp_action_events.csv, last filing 2026-10-09 per its note)
and counts events by type, universe and period. No price, NAV or return of any
date is read, so the 2023+ counts touch no holdout statistic.

Run (from the worktree root):  python3 -B results/cef/screens_2026-11-02/alpha_events_census.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alpha_common as ac  # noqa: E402


def main() -> int:
    e = pd.read_csv(ac.WT / "results" / "events" / "cef_corp_action_events.csv")
    e["tk"] = e["ticker"].fillna(e["ticker_now"])
    e["ann_date"] = pd.to_datetime(e["ann_date"], errors="coerce")
    c4 = pd.read_csv(ac.WT / "results" / "cef" / "c4" / "c4_universe_frozen_2026-10-14.csv")["ticker"].tolist()
    U = {"core deployed 13": list(ac.UNIVERSE), "WIDE17": ac.WIDE17, "C4 frozen 74": c4}
    print(f"census rows {len(e)}; undated rows {int(e.ann_date.isna().sum())} (mostly rights offerings: "
          f"{int((e.ann_date.isna() & (e.type == 'rights_offering')).sum())})")
    for lab, names in U.items():
        s = e[e.tk.isin(names)]
        fit = s[(s.ann_date >= "2005-01-01") & (s.ann_date <= ac.FIT_END)]
        post = s[s.ann_date > ac.FIT_END]
        tab = pd.DataFrame({"2005-22": fit.groupby("type").size(), "2023-26 (count only)": post.groupby("type").size()}).fillna(0).astype(int)
        print(f"\n{lab} ({len(names)} names):\n{tab.to_string() if len(tab) else '  none'}")
    rights = e[e.type == "rights_offering"]
    hit = rights[rights.fund.str.contains("PIMCO|BlackRock Corporate High Yield|DoubleLine|AllianceBernstein", case=False, na=False)]
    print(f"\nrights offerings naming a core sponsor's fund (undated in the census): {len(hit)}: "
          f"{'; '.join(hit.fund.unique())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
