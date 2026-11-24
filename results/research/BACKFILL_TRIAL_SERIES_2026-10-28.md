# Past trials' daily P&L series backfilled into the registry: EVENTS, XASSET, CEF, 2026-10-28

**Reproducer:** `python3 -m scripts.research.backfill.backfill stage && python3 -m scripts.research.backfill.backfill run --record`
(`scripts/research/backfill/backfill.py`; the census is `scripts/research/backfill/census.py`; tests
`python3 -m pytest scripts/research/tests/test_backfill.py`). It takes about a minute. It was recorded at `0eaedfa` on a clean
tree and wrote `results/research/backfill/backfill_2026-10-28.json`. `stage` copies each trial's gitignored caches in from
the worktrees `trial-events-e1` (6d8bdbf), `trial-events-navtender` (ac2c7ca), `trial-xasset`, `trial-c5` and `trial-c4`.
It refuses to replace a cache file that differs, and `data/` must be linked as in the other worktrees.
**Zero trials. No counter, spec or `docs/RESEARCH_STATE.md` edit. Fit period only: no 2023+ return was read for a stored
series, and E1's unopened holdout was not touched. It decides nothing.**

The ruling is the team lead's of 2026-10-27, `docs/SYSTEM.md` §5, row "Trial P&L series": **backfill what is reproducible.**
Branch `research-backfill` is `origin/research-reopen-book` with `origin/main` merged in. Every figure marked **[V]** comes from
the reproducer's run. **[S]** marks a figure read from a trial's committed note or fit JSON.

## 0. The answer

| counter | canonical trials | STORED | NOT REBUILT | `paper_bar_may_gate` | rho_bar | N_eff | V[SR] (per period) | common T |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| EVENTS | 2 | **2** | 0 | **True** | +0.0060 | 1.994 | 5.27e-05 | 3,217 |
| XASSET | 4 | **4** | 0 | **True** | +0.1868 | 3.440 | 4.99e-04 | 3,693 |
| CEF | 52 | **2** | 50 | **False** (coverage 2/52) | −0.0122 (floored at 0) | 2.000 | 1.23e-04 | 1,762 |

All figures [V], from `registry.bar_inputs(counter)` after the backfill (§3).

- **EVENTS and XASSET are fully covered.** Under the 2026-10-27 ruling, the paper's deflated-Sharpe bar may now gate them.
  `bar_inputs` measures coverage at every call, so a third EVENTS trial must store its series when it runs, or coverage
  falls below 1 and the desk's √(2 ln N) gates again. XASSET's slate is closed at N = 4.
- **CEF stays on the desk's bar.** Two of its 52 trials can be rebuilt: C5 (CEF-51) and C4 (CEF-52).
  - **The binding blocker: every committed CEF headline before C4 and C5 used data from 2023 on.** Trials 1–18 ran on
    the full sample to 2026. Trials 19–47 fitted on 2005-01 to 2023-12-31. Trials 48–50 report traded eras ending in
    2026-09. Reproducing any of those headlines would open the sealed 2023 time holdout.
  - Trials 1–47 also fail on every other count:
    - their identity inside each block is unrecorded (the counter has no trial log);
    - their scripts were deleted in the clean slate;
    - the 2026-07-31 panels have been refetched since (`data/cef/` keeps a `.pre-20261015.bak` of the price and NAV
      panels, and `results/cef/FRONTIER_REPRO_2026-10-07.md` records panel fixes after 2026-09-06);
    - trials 1–18 were scored at `shift(1)`.
  - **CEF-48..50: every pre-2023 figure their notes committed reproduces, 19 of 19, on panels cut at 2022-12-30**
    (§4, report only). Storing them on that check needs a ruling, because it is not the committed headline. Even then
    CEF would cover 5 of 52 and would not gate.

### Team lead, 2026-10-28, on this note

- **The paper's bar, once a counter qualifies, is computed with safeguards.** N is the declared slate
  size adjusted by ρ̄, and V is floored at 1/T (`inference.safeguarded_sr0`). EVENTS' measured V
  (5.27e-05 from two trials) is below the null 1/T (3.11e-04), so the floor binds. Hurdles
  (annualised): EVENTS 0.363, against the desk's 0.530 at this T; XASSET 0.337, against 0.435.
  Unfloored at the registry's N_eff, EVENTS would be 0.060. [V], from `bar_inputs` on this ledger,
  pinned in `test_safeguarded_sr0_reproduces_the_2026_10_28_bars`.
- **CEF keeps the desk's bar.**
- Recorded in `docs/SYSTEM.md` §5. CEF-48..50 (§4) were not stored; their storage was not ruled on,
  because it would not change CEF's gate.

## 1. What was stored, and how each was checked

Each rebuild calls the trial's **own** functions, in the order its fit entry point calls them, and stops at the series.
Every figure it can recompute is compared with the trial's committed fit JSON at 1e-9, and every one matched exactly
(max |diff| 0.0). Where the trial cached its series, the rebuilt series is also compared with that cache value for value.

The second method is reported beside the check and never decides. It is `scripts/research/inference.py::newey_west_t`,
run on the stored series, against the trial's committed t. The third column is the registry's own Sharpe, from the
ledger, against the committed headline.

| id | variant stored | span, T [V] | own-code reproduction [V] | inference NW t vs committed | ledger SR [V] vs headline [S] |
|---|---|---|---|---|---|
| EVENTS-1 | `e1_muni_tradable`: E1's muni tradable sleeve, total returns | 2009-06-23..2022-12-30, 3,406 | `extract_trial_series.py e1`: 11 figures of `e1_fit_verdict.json` (gross, nets, turn, ann, vol, T, k, harness_turn, deals) | L 21: 1.6516 = 1.6516 | 0.2808 vs 0.281 |
| EVENTS-2 | `navtender_tradable`: tradable sleeve, total returns | 2010-03-24..2022-12-30, 3,217 | `extract_trial_series.py navtender`: 9 figures of `fit_2026-10-19.json` | L 21: 2.1505 = 2.1505 | 0.4501 vs 0.450 |
| XASSET-1 | `x1_sized`: X1, sized and uncapped (decides) | 2008-05-02..2022-12-30, 3,693 | `runner.decide` stages 0b–5 and preflight: 190 figures and the verdict; cached series identical; manifest hashes verified | L 21: 1.6217 = 1.6217 | 0.4140 vs 0.41 |
| XASSET-2 | `x3_sized`: X3 | 2002-09-04..2022-12-30, 5,118 | 228 figures; cache identical | 4.9350 = 4.9350 | 1.0364 vs 1.04 |
| XASSET-3 | `x2_sized`: X2 | 2002-09-04..2022-12-30, 5,118 | 231 figures; cache identical | 1.5918 = 1.5918 | 0.3332 vs 0.33 |
| XASSET-4 | `x4_sized`: X4 | 2005-12-02..2022-12-30, 4,299 | 344 figures; cache identical | 1.9642 = 1.9642 | 0.4535 vs 0.45 |
| CEF-51 | `c5_G_wide`: C5's gain G on WIDE's holdings path | 2016-01-04..2022-12-30, 1,762 | `FitData`, `gain`, `stage1` on the frozen copy (141 files re-verified against `c5_frozen_inputs_2026-10-14.json`): 25 figures of stage 1; cached G identical | L 21: 2.8158 = 2.8158 | 1.1592 vs 1.16 |
| CEF-52 | `c4_74_declared`: C4's declared book, 74 funds (65 with fit data) | 2005-02-22..2022-12-30, 4,497 | `build_book`, `run_book` and stage 1 on panels cut at 2022-12-30: 72 figures (stage 1, cost grid, eras, funds with fit data); cached fit P&L identical | L 21: 5.3173 = 5.3173 | 1.2170 vs 1.217 |

Every ledger line carries commit `0eaedfa` and `dirty: false`. The params record the trial tree and head, the script, the
committed JSON, k and the turnover.

**E1's turnover.** The P&L stored is right. In `params`:
- `turn_event_ann` 2.63/yr [V]: the event turnover E1 charged costs on;
- `harness_turn_sized_ann` 4.21/yr [V]: the harness count, measured on the sized, capped Ht the P&L is earned on;
- `harness_turn_committed_raw_H_ann_MISSCALED` 14.40/yr [S]: the committed figure, measured on the raw H
  (`results/research/REOPEN_BOOK_NAVTENDER_E1_2026-10-28.md`).

## 2. The census

The census is one row per id in `census.py` (`python3 -m scripts.research.backfill.backfill census`). Ids whose rows
are identical are grouped here. `run` refuses unless the census covers exactly 1..N for the N it reads from the
counter table at run time.

**How the CEF ids were mapped.** The counter read 18 at the end of 2026-07-31 (`git show 1335a91:RESEARCH_STATE.md`).
The 2026-09-09 correction added the +29 from `ESTIMATOR_NOTE.md` and the band trial: 18 + 29 + 1 = 48. Then come
v7 (49, 50), C5 (51) and C4 (52). Inside each block below, **which configuration is which id is not recorded**. The
relative order of the 18 and the 29, all from 2026-07-31, is not recorded either. The nextgen branch's "CEF 53–56"
were ruled shadow research on 2026-09-28 and are not on this counter.

| id | trial | source (`pre-clean-slate:` = git tag) | script | status | reason | reproduction check |
|---|---|---|---|---|---|---|
| EVENTS-1 | E1, NAV-for-NAV CEF merger pair, muni tradable sleeve | `docs/RESEARCH_STATE.md` 2026-10-19; `e1_fit_verdict.json` (trial-events-e1) | `scripts/events/e1_merger_pair.py` via `extract_trial_series.py` | **STORED** | — | exact, 11 figures; NW t equal |
| EVENTS-2 | NAV tenders, tradable sleeve | as above; `fit_2026-10-19.json` (trial-events-navtender) | `scripts/events/nav_tender_trial.py` via the extractor | **STORED** | — | exact, 9 figures; NW t equal |
| XASSET-1..4 | X1, X3, X2, X4 in that order (the counter's order, `docs/RESEARCH_STATE.md` 2026-10-14) | `results/xasset/trials/x*_fit_2026-10-14.json` | `scripts/xasset/x*_*.py` → `runner.decide` | **STORED** | — | exact, 190 / 228 / 231 / 344 figures; caches identical |
| CEF-1..10 | day-one sleeve specifications, 2026-07-31 (own-history z long/short; hold, basket, \|z\|-threshold, PIT and v2/v3 variants) | `pre-clean-slate:results/AUDIT_2026-07-31.md` row 4; `pre-clean-slate:_archive/docs/RESEARCH_STATE_2026-09-14.md` ("10 specifications") | `pre-clean-slate:_archive/scripts/_archive/cef_sleeve*.py`, `scripts/cef/discount_test.py`, `validate.py` | NOT REBUILT | ambiguous identity (more than ten configurations named); script deleted; `shift(1)`; full-sample headline spans the 2023 holdout; panel changed | not attempted |
| CEF-11..16 | execution and niche-edge variants, 2026-07-31 (bands, holds, price weighting, January basis sleeve, distribution events) | `pre-clean-slate:results/cef/research/NICHE_EDGE_RESEARCH.md` §6 ("10 → 16") | none named | NOT REBUILT | ambiguous identity (12+ named, 6 counted); no script in git; `shift(1)`; headline spans the holdout; panel changed | not attempted |
| CEF-17..18 | two trials between 16 and 18, not itemised anywhere (the AUDIT's hold sweep is a candidate, unconfirmed) | `1335a91:RESEARCH_STATE.md`; `pre-clean-slate:results/AUDIT_2026-07-31.md` §3 | unknown | NOT REBUILT | identity unknown; script deleted; headline spans the holdout; panel changed | not attempted |
| CEF-19..27 | distribution-cut study: 1 event study + 8 filters | `pre-clean-slate:results/cef/DIST_CUT_NOTE.md` ("+9") | `pre-clean-slate:scripts/cef/dist_cut_study.py` | NOT REBUILT | ambiguous (the table shows 6 rules + baseline against "eight"); script deleted; sweep runs to the panel end; panel changed | not attempted |
| CEF-28..43 | Kalman state-space sweeps | `pre-clean-slate:results/cef/ESTIMATOR_NOTE.md` ("16 Kalman sweeps") | `pre-clean-slate:scripts/cef/kalman_discount.py` | NOT REBUILT | sweeps not listed one by one; script deleted; fit 2005-01..**2023-12-31** spans the holdout; panel changed | not attempted |
| CEF-44..47 | rolling-z window control, windows 21/63/126/252 | same note ("4 window control") | same script | NOT REBUILT | order unrecorded; script deleted; fit to 2023-12-31; panel changed | not attempted |
| CEF-48 | band 4.8% replaces the 2d calendar (v6), 17 names | `results/cef/PREREG_BAND_2026-09-06.md`; `FRONTIER_REPRO_2026-10-07.md` §A | `scripts/cef/band_frontier.py` | NOT REBUILT | headline: 5,452 sessions to 2026-09-03, spans the holdout; the prereg commits no fit-only Sharpe | report only: the v6 17-name book's pre-2023 figures in the v7 note reproduce (§4) |
| CEF-49 | universe 17 → 13 (band, uncapped) | `results/cef/PREREG_ALPACA_V7_2026-09-28.md` | `scripts/cef/alpaca_v7_derivation.py` | NOT REBUILT | headline: traded era to 2026-09-21, spans the holdout; no fit-only Sharpe committed for this book | report only: w5 0.0425814 ending 2020-03-18, k 0.00 and 7.4% reproduce (§4) |
| CEF-50 | `max_gross_stress` 1.80 on the 13-name band | same | same | NOT REBUILT | headline spans the holdout | report only: the three fit-era rows reproduce (§4) |
| CEF-51 | C5, t+1 opening-auction fill (G) | `results/cef/C5_RESULT_2026-10-14.md` | `scripts/cef/c5_open_auction.py` | **STORED** | — | exact, 25 figures; cached G identical; NW t equal |
| CEF-52 | C4, five CEF families, 74 frozen funds | `results/cef/C4_RESULT_2026-10-14.md` | `scripts/cef/c4_families.py` | **STORED** | — | exact, 72 figures; cached P&L identical; NW t equal |

## 3. `bar_inputs(counter)` after the backfill [V]

```
EVENTS: canonical_trials 2, stored_trials 2, coverage 1.0, paper_bar_may_gate True, variants 2, T 3217,
        dropped_sessions 189, rho_bar 0.005957, n_effective 1.9940, sr_var 5.2728e-05, ill_conditioned False
XASSET: canonical_trials 4, stored_trials 4, coverage 1.0, paper_bar_may_gate True, variants 4, T 3693,
        dropped_sessions 1425, rho_bar 0.186825, n_effective 3.4395, sr_var 4.9947e-04, ill_conditioned False
CEF:    canonical_trials 52, stored_trials 2, coverage 0.0385, paper_bar_may_gate False, variants 2, T 1762,
        dropped_sessions 2735, rho_bar -0.012228, n_effective 2.0000, sr_var 1.2262e-04, ill_conditioned False
```

- `sr_var` is the variance of the per-period (daily) Sharpe ratios across the stored variants. It follows
  `inference.py`'s convention: per period unless a name ends `_annual`.
- `T` is the sessions all of a counter's variants share:
  - XASSET's starts at X1's first P&L, 2008-05-02.
  - CEF's is C5's window, 2016–22.
  - **CEF's measured inputs describe 2 of 52 trials, and are not the search's.**

## 4. CEF-48..50: their pre-2023 figures, on panels cut at 2022-12-30 (report only)

`cef_v7_fit_check()` cuts the four CEF panels on read: prices and NAV to 2022-12-30, distributions to 2022-12-28, and no
split row before 2023. It then runs `alpaca_v7_derivation.py`'s own functions on the v6 17-name universe (read from tag
`spec-cef_discount.v6.20260906`) and on the 13 names. It compares every figure `PREREG_ALPACA_V7_2026-09-28.md`
committed that uses only pre-2023 data, at that figure's stated precision [V]:

| figure | committed [S] | rebuilt [V] |
|---|---|---|
| 17-name k (median \|muni − taxable\| on targets, 2013-06-14..2022-12-30) | 0.304953 | 0.304953 |
| 17-name w5, ending | 0.038264817497540925, 2020-03-18 | identical to 1e-12, 2020-03-18 |
| 13-name k; muni target share | 0.00; 7.4% | 0.00; 7.4% |
| 13-name w5 (CEF-49's book), ending | 0.0425814, 2020-03-18 | 0.0425814, 2020-03-18 |
| v6 band, 17 names, gross SR (ann %), 2010–14 / 2015–19 / 2020–22 | 0.86 (2.7) / 1.48 (9.9) / 2.17 (16.0) | the same |
| v7-on-Alpaca (CEF-50's book), 2010–14 / 2015–19 / 2020–22 | 0.72 (2.2) / 0.82 (5.6) / 1.06 (6.7) | the same |

**What this would and would not license.** It shows that the fit-period part of these books is what those trials ran on.
It is not their headline, so nothing was stored.
- If the team lead accepted these figures as the reproduction check, `backfill.py` could store:
  - CEF-50 (the capped 13-name book);
  - CEF-49 (the uncapped 13-name band, on w5 alone);
  - CEF-48 (the v6 17-name band; its era rows come from the v7 note, which scores it on total returns, while trial
    48's own prereg scored it on price returns).
- CEF would then cover 5 of 52, and its gate stays False.

## 5. Deviations, caveats and what was not done

- **C4's path differs from its fit in two ways, both proved harmless by the exact reproduction.** The fit built targets
  on the full families panel (to 2026-10-09) and sliced them afterwards; here the panels are cut at 2022-12-30 on read.
  1. The nine frozen funds with no pre-2023 row (BSTZ, BTX, GUG, HGLB, IGA, KYN, NPFD, NXG, TBLD, the committed
     list) then have no column. They enter as zero target columns, which is what the full panel gives them before 2023.
  2. `crsp_returns()`'s gate, which requires the extract to reach 2024-12-31, is not called: it checks holdout coverage.
     The extract is read cut at 2022-12-30.
- **XASSET** reads its staged panel through the trial's own loader. That loader holds the whole file, and `runner.load`
  truncates it before any statistic. The holdouts were opened on 2026-10-14/15; nothing from 2023 on was computed or
  stored here.
- **One variant per trial.** The registry clusters over variants for the effective N, so each trial stores only the
  series its verdict was judged on. The capped, price-return and report-only views are not stored.
- **The series live only on this machine.** `results/research/trials/series/` is gitignored, as the registry requires.
  The tracked `ledger.jsonl` carries each series' sha256, and `registry.load` refuses a file that no longer matches.
- **No trial worktree was written.** `git status` is clean in all five, and no file in them is newer than this run's
  helper. Each source cache is only read, and `stage` refuses to overwrite a differing copy.
- **Statistics.** The reproduction necessarily uses each trial's own functions. The only new statistic is
  `inference.newey_west_t`. The ledger's Sharpe, skew and kurtosis are the registry's own.
- **Second method, NAV tenders.** Its committed `nw_t` is at L 21 (`NW_LAGS`), with `nw_auto_lag` 8 reported beside it.
  A first run compared at lag 8 and read 1.986 against 2.150. That was the wrong lag; at L 21 the two are equal.
- Offline throughout. `ops.netguard` was installed in the process and in the EVENTS child. No R2, no network, no broker.
