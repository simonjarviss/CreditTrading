"""The census of every canonical trial on EVENTS, XASSET and CEF: what it was, where
it is recorded, the script that ran it, and whether its daily series can be rebuilt.

WHY THIS FILE EXISTS (2026-10-28). The team lead ruled (`docs/SYSTEM.md` §5,
2026-10-27, row "Trial P&L series"): **backfill what is reproducible**. The paper's
deflated-Sharpe bar may gate a counter only once every canonical trial on it has a
stored series (`scripts/research/registry.py::bar_inputs` -> `paper_bar_may_gate`).
So each trial id `<COUNTER>-<n>`, 1 <= n <= the counter's canonical count, needs a
row saying either "rebuilt by <function>" or why it cannot be. This file is that
list, kept as data so `backfill.py` can check at run time (H14) that it covers the
canonical count read from `docs/RESEARCH_STATE.md`, and so the note and the code
cannot disagree.

HOW THE CEF IDS WERE MAPPED. The CEF counter has no trial log. Its history, read
from git (tag `pre-clean-slate` for everything before 2026-09-28):
- it read 18 at the end of 2026-07-31 (`git show 1335a91:RESEARCH_STATE.md`), made of
  "10 specifications" on day one (`pre-clean-slate:results/AUDIT_2026-07-31.md` row 4;
  `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` "SEARCH STOPPED HERE at
  10 specifications"), "10 -> 16" in `pre-clean-slate:results/cef/research/
  NICHE_EDGE_RESEARCH.md` §6, and two more that no surviving record itemises;
- the 2026-09-09 correction added the +29 that `pre-clean-slate:results/cef/
  ESTIMATOR_NOTE.md` recorded the same day (9 distribution-cut + 16 Kalman sweeps +
  4 window control) and the band trial: 18 + 29 + 1 = 48;
- 49 and 50 are `results/cef/PREREG_ALPACA_V7_2026-09-28.md`; 51 is C5, 52 is C4
  (`docs/RESEARCH_STATE.md`).
The ids below follow that arithmetic. Inside a block (1-10, 11-16, 17-18, 19-27,
28-43, 44-47) which configuration is which id is NOT recorded, and the relative
order of the 18 and the 29 within 2026-07-31 is not recorded either. Every row in
those blocks says so ("ambiguous identity"). The nextgen branch's "CEF 53-56"
(2026-09-14/16) are not on this counter: the team lead ruled on 2026-09-28 that
`main`'s 48 was authoritative and the nextgen trials were shadow research.

STATUS. `REBUILD` names the function in `backfill.py` that re-runs the trial's
committed fit path; the run turns it into STORED only after the re-run reproduces
the committed headline. Everything else is `NOT REBUILT`, with every reason that
applies.
"""
from __future__ import annotations

REBUILD, NOT_REBUILT = "REBUILD", "NOT REBUILT"

# Reasons, so the note's table and the code say the same words.
R_HOLDOUT = ("its committed headline spans the sealed 2023 time holdout, so reproducing it "
             "would open the holdout")
R_PANEL = "panel changed: the 2026-07-31 panels were refetched and replaced since"
R_SCRIPT_GONE = "script deleted in the 2026-09-28 clean slate (recoverable only at tag pre-clean-slate)"
R_NO_SCRIPT = "no script in git names this work (it predates the repository's first commit)"
R_SHIFT1 = "scored at shift(1), the lookahead fixed 2026-09-10; a faithful rebuild reproduces the artifact"
R_AMBIG = "ambiguous identity: the record does not say which configuration this id is"

_ARCH_RS = "pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md"


def _block(lo: int, hi: int, trial: str, source: str, script: str, reasons: list[str]) -> list[dict]:
    return [dict(id=f"CEF-{n}", trial=f"{trial} ({n - lo + 1} of {hi - lo + 1}; which one is unrecorded)",
                 source=source, script=script, status=NOT_REBUILT, reason="; ".join(reasons), rebuild=None)
            for n in range(lo, hi + 1)]


EVENTS = [
    dict(id="EVENTS-1", trial="E1: NAV-for-NAV CEF merger pair, muni headline, tradable sleeve",
         source="docs/RESEARCH_STATE.md (2026-10-19: 'EVENTS trial 1 is E1'); "
                "results/events/e1/e1_fit_verdict.json on branch trial-events-e1",
         script="scripts/events/e1_merger_pair.py (trial-events-e1), via "
                "scripts/research/reopen_book/extract_trial_series.py e1",
         status=REBUILD, reason="", rebuild="events_e1"),
    dict(id="EVENTS-2", trial="NAV tenders: tradable sleeve",
         source="docs/RESEARCH_STATE.md (2026-10-19: 'EVENTS trial 2 is NAV tenders'); "
                "results/events/nav_tender/fit_2026-10-19.json on branch trial-events-navtender",
         script="scripts/events/nav_tender_trial.py (trial-events-navtender), via "
                "scripts/research/reopen_book/extract_trial_series.py navtender",
         status=REBUILD, reason="", rebuild="events_navtender"),
]

# docs/RESEARCH_STATE.md, "2026-10-14: XASSET counter moves, one commit before each
# test's Stage 0b": 0 -> 1 X1, 1 -> 2 X3, 2 -> 3 X2, 3 -> 4 X4.
XASSET = [
    dict(id=f"XASSET-{n}", trial=f"{key}: {title}, sized uncapped sleeve (the series that decides)",
         source=f"results/xasset/trials/{key.lower()}_fit_2026-10-14.json; results/xasset/XASSET_RESULTS_2026-10-14.md",
         script=f"scripts/xasset/{mod}.py (runner.decide)", status=REBUILD, reason="", rebuild=f"xasset:{key}")
    for n, key, title, mod in ((1, "X1", "credit and rates trend", "x1_credit_trend"),
                               (2, "X3", "month-end Treasury extension", "x3_month_end"),
                               (3, "X2", "pension rebalancing front-run", "x2_rebalancing"),
                               (4, "X4", "multi-asset trend", "x4_multi_trend"))
]

CEF = (
    _block(1, 10, "day-one CEF discount sleeve specification, 2026-07-31: the long/short book on each fund's "
                  "own 252d discount z, with its hold, basket, |z|-threshold, point-in-time-universe and "
                  "v2/v3 (vol-target, group-neutral) variants",
           f"pre-clean-slate:results/AUDIT_2026-07-31.md row 4 ('10 specs'); {_ARCH_RS} 'CEF DISCOUNT "
           "REVERSION' and 'CEF v2/v3' ('SEARCH STOPPED HERE at 10 specifications')",
           "pre-clean-slate:_archive/scripts/_archive/cef_sleeve.py, cef_sleeve_v2.py; "
           "pre-clean-slate:scripts/cef/discount_test.py, validate.py",
           [R_AMBIG + " (the record names more than ten configurations)", R_SCRIPT_GONE, R_SHIFT1,
            R_HOLDOUT + " (full sample 2005-2026)", R_PANEL])
    + _block(11, 16, "execution and niche-edge variants, 2026-07-31: no-trade bands 1%/5%, holds 10/21/42d, "
                     "price weighting and its four alternatives, the January hedged basis sleeve, "
                     "distribution events",
             "pre-clean-slate:results/cef/research/NICHE_EDGE_RESEARCH.md §6 ('Trial counter on this "
             "data source: 10 -> 16')",
             "none named in the note",
             [R_AMBIG + " (twelve or more configurations named, six counted)", R_NO_SCRIPT, R_SHIFT1,
              R_HOLDOUT + " (full sample)", R_PANEL])
    + _block(17, 18, "two trials between NICHE_EDGE_RESEARCH's 16 and the 18 the table read at the end of "
                     "2026-07-31; one candidate is the AUDIT's hold sweep (hold 1/2/5/21), unconfirmed",
             "git show 1335a91:RESEARCH_STATE.md (CEF 18); pre-clean-slate:results/AUDIT_2026-07-31.md §3",
             "unknown (pre-clean-slate:scripts/audit/cef_cost_frontier.py if the hold sweep)",
             [R_AMBIG + " (no record itemises 17 and 18)", R_SCRIPT_GONE, R_HOLDOUT, R_PANEL])
    + _block(19, 27, "distribution-cut study, 2026-07-31: 1 event study + 8 exclusion-filter variants",
             "pre-clean-slate:results/cef/DIST_CUT_NOTE.md ('CEF counter +9'); "
             "pre-clean-slate:results/cef/ESTIMATOR_NOTE.md 'Trial accounting'",
             "pre-clean-slate:scripts/cef/dist_cut_study.py",
             [R_AMBIG + " (the note's table shows six exclusion rules and a baseline against its 'eight')",
              R_SCRIPT_GONE, R_HOLDOUT + " (the sweep runs to the panel end)", R_PANEL])
    + _block(28, 43, "Kalman state-space discount sweeps, 2026-07-31 (lam grids, cut-inflation on/off)",
             "pre-clean-slate:results/cef/ESTIMATOR_NOTE.md ('16 Kalman sweeps')",
             "pre-clean-slate:scripts/cef/kalman_discount.py",
             [R_AMBIG + " (sixteen sweeps, not listed one by one)", R_SCRIPT_GONE,
              R_HOLDOUT + " (fit 2005-01 .. 2023-12-31)", R_PANEL])
    + _block(44, 47, "rolling-z window control, 2026-07-31: z windows 21/63/126/252",
             "pre-clean-slate:results/cef/ESTIMATOR_NOTE.md ('4 window control'); its 2024+ holdout "
             "(pre-clean-slate:results/cef/HOLDOUT_OPENED.json) adjudicated z_window=63",
             "pre-clean-slate:scripts/cef/kalman_discount.py",
             [R_AMBIG + " (the four windows are named, their order is not)", R_SCRIPT_GONE,
              R_HOLDOUT + " (fit 2005-01 .. 2023-12-31)", R_PANEL])
    + [
        dict(id="CEF-48", trial="no-trade band 4.8% replaces the 2-day calendar (spec v6), 17 names",
             source="results/cef/PREREG_BAND_2026-09-06.md ('Trial 48'); "
                    "results/cef/FRONTIER_REPRO_2026-10-07.md §A",
             script="scripts/cef/band_frontier.py",
             status=NOT_REBUILT, rebuild=None,
             reason=R_HOLDOUT + " (5,452 sessions to 2026-09-03); the prereg commits no fit-only Sharpe "
                    "for this book"),
        dict(id="CEF-49", trial="universe 17 -> 13 (NAD, NEA, NVG, NZF unshortable at Alpaca), band 4.8%",
             source="results/cef/PREREG_ALPACA_V7_2026-09-28.md (trial 1 of 2)",
             script="scripts/cef/alpaca_v7_derivation.py",
             status=NOT_REBUILT, rebuild=None,
             reason=R_HOLDOUT + " (traded era 2013-06-14 .. 2026-09-21); no fit-only Sharpe is committed "
                    "for the uncapped 13-name book (only its w5, checked as report-only)"),
        dict(id="CEF-50", trial="max_gross_stress 1.80 on the 13-name band (v7-on-Alpaca)",
             source="results/cef/PREREG_ALPACA_V7_2026-09-28.md (trial 2 of 2)",
             script="scripts/cef/alpaca_v7_derivation.py",
             status=NOT_REBUILT, rebuild=None,
             reason=R_HOLDOUT + " (traded era 2013-06-14 .. 2026-09-21); its fit-period era rows are "
                    "checked as report-only, a ruling would be needed to store on them"),
        dict(id="CEF-51", trial="C5: t+1 opening-auction fill, the gain G on WIDE's holdings path",
             source="results/cef/C5_RESULT_2026-10-14.md; results/cef/c5/C5_FIT_VERDICT.json",
             script="scripts/cef/c5_open_auction.py (FitData, gain, stage1) on the frozen copy",
             status=REBUILD, reason="", rebuild="cef_c5"),
        dict(id="CEF-52", trial="C4: the live z pooled over five CEF families, 74 frozen funds (declared book)",
             source="results/cef/C4_RESULT_2026-10-14.md; results/cef/c4/c4_fit_verdict_2026-10-14.json",
             script="scripts/cef/c4_families.py (build_book, run_book) on panels cut at 2022-12-30",
             status=REBUILD, reason="", rebuild="cef_c4"),
    ]
)

CENSUS = {"EVENTS": EVENTS, "XASSET": XASSET, "CEF": CEF}


def validate(counter: str, canonical: int) -> list[dict]:
    """The counter's rows, after checking they are exactly <COUNTER>-1 .. -<canonical>,
    each with a known status, a reason when not rebuilt and a rebuilder when rebuilt.
    `canonical` is read at run time from the counter table (H14), never written here."""
    if counter not in CENSUS:
        raise KeyError(f"no census for counter {counter!r}")
    rows = CENSUS[counter]
    want = [f"{counter}-{n}" for n in range(1, canonical + 1)]
    got = [r["id"] for r in rows]
    if got != want:
        missing, extra = sorted(set(want) - set(got)), sorted(set(got) - set(want))
        raise ValueError(f"{counter} census does not cover its canonical count {canonical}: "
                         f"missing {missing[:5]}, extra {extra[:5]}; add a row for each new trial")
    for r in rows:
        if r["status"] not in (REBUILD, NOT_REBUILT):
            raise ValueError(f"{r['id']}: unknown status {r['status']!r}")
        if r["status"] == NOT_REBUILT and not r["reason"]:
            raise ValueError(f"{r['id']}: NOT REBUILT needs a reason")
        if r["status"] == REBUILD and not r["rebuild"]:
            raise ValueError(f"{r['id']}: REBUILD needs a rebuilder")
    return rows
