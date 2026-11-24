# Live turnover vs the live band policy (report only, 2026-11-02)

Written to disk by the main session from the workflow's final report (the subagent could not write it), 2026-11-02.

> **The review found a real defect, so the fit-era numbers for "the live policy" are not established.**
> - The harness and the live sleeve treat thin sessions differently. A thin session is one with fewer than `min_names` = 6 eligible names.
>   - The canonical harness **holds** the previous target on such a session (`scripts/cef/band_frontier.py:206`).
>   - The live sleeve **flattens** (`src/deploy/sleeves/cef_discount.py:892-895`). The spec has `min_names: 6` and no `below_min_names` key, which means flatten.
> - Thin, held books earn 3,484 of the 4,531 fit-period P&L days [V]. Those days carry 1.41 of the fit period's 3.29%/yr [V], and 3.99 of the 5.70%/yr in 2015-19 [V].
> - The tables below keep the first-pass rows, labelled **"hold (harness)"**. Beside them is a replica of the live flatten rule, labelled **"flatten (replica)"**. The replica is the reviewer's, and I re-ran it for this report. It is a replica, not the sleeve.
> - This is defect A1 of `results/cef/ALPHA_LEAKAGE_2026-10-13.md` [S]. The first pass re-derived that note's L2 and A2 but not A1.
>
> **Independent re-derivation: AGREE** on every hold-rule figure checked: fit, H13, full, the three eras and the 5/15/30bp grid. That agreement does not cure the defect, because both passes scored the hold rule.

**Labels:**
- [V] re-run in this workflow on the repo panels.
- [V parent] the parent session's Alpaca fill figures, which this workflow did not read.
- [U] arithmetic on an approximate input.
- [S] quoted, not re-run.

Zero trials, no spec change, nothing committed. Branch `research-turnover-study`. `data/` was not written: the panel file times are unchanged [V]. Prices and NAV are at 2026-10-15 16:24; distributions and splits at 2026-09-11 10:48.

## Answers

### 1. Turnover: the defect does not change this answer
- **Live vs policy.** The live rate of about 58.7/yr [U] is above the policy's 2023+ mean of 44.7 to 45.9/yr [V]. It matches the policy's trailing-year rate: 57.2/yr with instant flips, 54.3/yr with deferred flips [V].
- **Opening build.** About 26% of the live window's trading is the one-off opening build [U]. Without it the live rate is about 43.6/yr [U].
- **Verdict.** I found no sign that the live book trades more than the policy.
- **Why the defect does not touch it.** There has been no thin session since 2026-09-28 [V]. The last-252-decision rate is 57.2/yr under both rules [V, reviewer].

### 2. Deferred flip: measured on the hold book only
- **A2 window:** the deferral costs −0.38pp/yr [V]. The leakage report also has −0.38pp [S].
- **2023+:** it costs −0.75pp/yr [V]. H13 has only 138 thin sessions, carrying −0.02%/yr of P&L [V]. So the H13 figure is probably close under the live rule, but that was not re-run [U].
- **Gap.** The fit and A2 deferral costs were not re-run under the flatten rule. The A2 window starts 2013-06-14, so it contains the thin 2015-19 era.

### 3. Cost grid: this answer reverses
- **First pass (hold rule).** The net sign flipped across the 5/15/30bp grid only in 2023+. It gave the reason as "turnover there is about six times the fit period's". That is not supported.
- **Live flatten rule** [V, replica]:
  - The net sign flips at 30bp in **every** era, including fit and H13.
  - In 2010-14 and 2015-19 it flips already at 15bp.
  - Fit break-even is **18.6bp**, against 45.8bp on the hold book. H13 break-even is 23.8bp under either rule.
  - So under the live rule, the fit-era cost case was weaker than H13's, not stronger.
- **"About six times" is wrong.** It comes from a fit row that includes 1,259 sessions in 2005-09 that held nothing. By era, H13's turnover is:
  - 2.1× 2020-22's on the hold book (44.7 vs 21.5) [V].
  - 1.8× on the flatten replica (44.7 vs 24.2) [V, replica].

## Panels and spec [V]
- **Spec.** `cef_discount.v7.20260928`: band 4.8%, gross ceiling 1.80×, `min_names` 6, 13 names. All read through `scripts/cef/spec.py`.
- **Panel last dates.** Prices end 2026-10-15 and NAV 2026-10-14, so targets end **2026-10-14**.
- **Distributions.** The last ex-date for any universe name is **2026-09-03** (AWF). The other names' last ex-dates are 2026-08-13 to 08-19. Every name pays on a 28-31 day cycle, so each name's next ex-date falls after 09-03. The cut is sound on this panel [V].
- **Return cut.** `total_returns` does not raise when the distribution panel ends before the price panel. So every return statistic is cut at **DIST_END = 2026-09-03**, and the script asserts it. Turnover comparisons use targets to 2026-10-14.
- **Staleness.** Both panels are stale against today, 2026-11-02.

## Definitions
- **Targets and scoring.** Targets come from `build_targets()`. Returns come from `total_returns(R)` and are scored by `evaluate()` with shift(2).
- **Hold (harness).** `band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)`.
  - On a thin session it holds the previous target.
  - Flips are "instant" (done within one session).
- **Flatten (replica).** The same band and ceiling (`_cap_gross` from the sleeve).
  - On a thin session every name goes to zero, and the band reopens from flat.
  - Eligibility is counted on z-score and ADV only. The live sleeve also drops names with stale NAV, so it has at least as many flat days [U].
  - Script: `results/backtests/turnover-live-2026-11-02/flatten_replica.py`, adapted from the reviewer's `rv2.py`.
- **Deferred flip.** `band_gross_capped(..., defer_flips=True)` copies `quantt/session/decide.py:332-342` with `FLIP_SAME_SESSION=False`.
  - If a name would cross zero from yesterday (`prev*cur<0`), it is held flat for that session.
  - This is applied after the band and the ceiling. The other names are not rescaled.
- **turn/yr** = Σ|H[t]−H[t−1]| × 252/n. This is `evaluate()`'s turn and the parent's live definition.
- **Net and break-even.** Net@c = ann − turn×c/1e4, at c = 5, 15 and 30bp. **BE** = ann/turn×1e4.
- **maxDD** is compounded.
- **Drag [U]** = turn × 5.5bp, the parent's measured paper fill drag.
- **No borrow is charged.** Gross is the headline.
- **FIT** is everything before 2023-01-01, starting 2005-01-03. It includes the empty 2005-09 era.
- **H13** is 2023-01-03 to 2026-09-03. Nothing is chosen from H13.

## (1)+(3) Live band policy, instant flip, total returns, both thin-day rules

Gross is the headline, with the cost grid beside it. Hold rows are [V]; flatten rows are [V, replica].

| window | rule | gross SR | ann % | vol % | maxDD % | turn/yr | net SR @5 / @15 / @30 | net %/yr @5 / @15 / @30 | sign flips? | BE bp | drag %/yr [U] |
|---|---|---:|---:|---:|---:|---:|---|---|---|---:|---:|
| 2005-09 | both | flat: held nothing | | | | 0.0 | | | | | |
| 2010-14 | hold | 0.72 | 2.24 | 3.12 | −4.5 | 5.2 | 0.63 / 0.47 / 0.22 | 1.98 / 1.46 / 0.69 | no | 43.3 | 0.28 |
| 2010-14 | **flatten** | 0.29 | 0.69 | 2.40 | −5.2 | 7.3 | 0.14 / −0.17 / −0.62 | 0.33 / −0.40 / −1.50 | **YES (15bp)** | 9.5 | 0.40 |
| 2015-19 | hold | 0.84 | 5.70 | 6.83 | −12.8 | 7.8 | 0.78 / 0.66 / 0.49 | 5.31 / 4.53 / 3.36 | no | 73.2 | 0.43 |
| 2015-19 | **flatten** | 0.38 | 0.95 | 2.48 | −6.6 | 8.7 | 0.21 / −0.15 / −0.67 | 0.51 / −0.36 / −1.68 | **YES (15bp)** | 10.8 | 0.48 |
| 2020-22 | hold | 1.02 | 6.49 | 6.36 | −4.3 | 21.5 | 0.85 / 0.51 / 0.01 | 5.41 / 3.27 / 0.05 | no | 30.2 | 1.18 |
| 2020-22 | **flatten** | 1.37 | 6.73 | 4.92 | −3.5 | 24.2 | 1.12 / 0.63 / −0.11 | 5.52 / 3.10 / −0.52 | **YES (30bp)** | 27.8 | 1.33 |
| FIT <2023 | hold | 0.69 | 3.29 | 4.73 | −12.8 | 7.2 | 0.62 / 0.47 / 0.24 | 2.93 / 2.21 / 1.13 | no | 45.8 | 0.39 |
| **FIT <2023** | **flatten** | **0.58** | **1.58** | **2.72** | **−6.6** | **8.5** | 0.42 / 0.11 / **−0.36** | 1.15 / 0.30 / **−0.97** | **YES (30bp)** | **18.6** | 0.47 |
| H13 2023+ | hold | 1.95 | 10.61 | 5.43 | −4.9 | 44.7 | 1.54 / 0.72 / −0.51 | 8.37 / 3.91 / −2.79 | YES (30bp) | 23.8 | 2.46 |
| H13 2023+ | flatten | 2.07 | 10.63 | 5.13 | −2.9 | 44.7 | 1.64 / 0.76 / −0.54 | 8.39 / 3.92 / −2.79 | YES (30bp) | 23.8 | 2.46 |
| full | hold | 0.93 | 4.52 | 4.86 | −12.8 | 13.5 | 0.79 / 0.51 / 0.10 | 3.85 / 2.50 / 0.47 | no | 33.5 | 0.74 |
| full | flatten | 0.95 | 3.11 | 3.26 | −6.6 | 14.6 | 0.73 / 0.28 / −0.39 | 2.38 / 0.92 / −1.28 | YES (30bp) | 21.3 | 0.80 |

- **How the rows were checked.**
  - The hold rows were reproduced three times: the first pass, `harness.report(nan_policy="raise")`, and an independent re-derivation on the committed HEAD harness [V].
  - The flatten rows have one implementation, re-run once. No second method has checked them. Treat them as [V, replica], not as established.
- **The hold rows before 2020 mostly reflect a stale book carried through thin stretches.** In 2015-19 the mean gross held on thin sessions is 1.33, against 1.18 on active sessions [V].
- **2020-22 is the only fit era where the live rule beats hold.** There, the thin-held days carried −0.60%/yr [V].
- **Thin-session counts [V].**
  - By era: 983 (2010-14), 908 (2015-19), 334 (2020-22), 138 (2023+), and none since 2026-09-28.
  - The 2023+ stretch runs 2023-02-13 to 08-30. Eight names fail the ADV floor throughout it.
- **Gross ceiling, hold book [V].**
  - It binds on 17.6% of 2023+ days. Those days carry 17.3/yr of the 45.9/yr (to 2026-10-14), so at most 38% of the turnover.
  - When it binds, the whole book is rescaled, so 38% is an upper bound on what the ceiling itself causes.
  - In the fit period it binds on 3.9% of days and carries 4% of turnover. That fit figure is on the hold book and was not re-run under flatten.

### Is about 58/yr in line with the policy's recent turnover? (re-derived; L2's 44.6 not used)

| measure | instant | deferred (as the live runner trades) |
|---|---:|---:|
| H13 return window (to 2026-09-03) | 44.7 | 42.1 |
| 2023 to 2026-10-14 | 45.9 | 43.3 |
| last 252 decisions | **57.2** | **54.3** |
| last 63 decisions | 52.1 | 50.0 |
| 24-session windows in 2023+, p05 / p50 / p95 / max | 0 / 39.8 / 109.2 / 159.4 | 0 / 38.1 / 98.3 / 148.0 |
| share of those windows at or above 58/yr | 30% | 30% |
| decisions 09-28..10-14 (13 of the 24 live sessions) | 98.6 | 89.1 |

All figures are [V], on the hold book. Under flatten, the reviewer reports 2023+ turnover of 46.0 against 45.9 under hold, and last-252 decisions at 57.2 under both [V, reviewer].

- **Live rate.** $558,927 [V parent] / ~$100k × 252/24 = **58.7/yr** [U].
- **Opening build.** The live book opened from flat to full target.
  - The harness target for the 2026-09-28 decision has gross **1.436**, and the ceiling does not bind [V].
  - That is 26% of the window's trading [U].
  - Without it: (5.59 − 1.44) × 252/24 = **43.6/yr** [U].
- **Verdict.** 58.7/yr is above the 2023+ mean but in line with the trailing-year rate. Without the build, it is in line with or below every recent measure.
- **The 13-session overlap (09-28..10-14) is not a clean comparator.** It is dominated by 10-05 and 10-06. On those two sessions:
  - the harness vol scalar hit its 2.5 clip;
  - the ceiling bound on all 13 names;
  - 2.14 turns traded [V].

## (2) Deferred flip minus instant flip, total returns, hold book only [V]

| window | flips/yr | gross SR inst→def | Δ ann pp | NW t | turn inst / def | Δ net pp @5 / @15 / @30 |
|---|---:|---|---:|---:|---|---|
| 2010-14 | 6.2 | 0.72→0.72 | +0.01 | 0.15 | 5.2 / 5.0 | +0.02 / +0.03 / +0.06 |
| 2015-19 | 15.2 | 0.84→0.82 | −0.09 | −0.55 | 7.8 / 7.6 | −0.08 / −0.06 / −0.03 |
| 2020-22 | 42.7 | 1.02→0.90 | −0.65 | −1.11 | 21.5 / 20.7 | −0.61 / −0.53 / −0.42 |
| FIT | 13.1 | 0.69→0.66 | −0.13 | −1.28 | 7.2 / 7.0 | −0.12 / −0.10 / −0.06 |
| H13 | 69.5 | 1.95→1.81 | −0.75 | −1.89 | 44.7 / 42.1 | −0.62 / −0.36 / +0.03 |
| full | 22.6 | 0.93→0.88 | −0.23 | −2.15 | 13.5 / 12.9 | −0.20 / −0.14 / −0.05 |
| A2 window, 2013-06-14+ | 37.0 | 1.19→1.12 | **−0.38** | −2.13 | 22.1 / 21.1 | −0.33 / −0.23 / −0.08 |

- **A2 is re-derived.** My run gives −0.38pp/yr, SR 1.19→1.12 and 37 flips/yr [V]. The leakage report had −0.38pp, 1.17→1.11 and about 37 [S].
- **Fit, the eras before 2020, and A2 are measured on the hold book.** Under the live flatten rule they are a gap (follow-up F3).
- **H13 break-even.** The deferral pays for itself only at about 29bp of cost: it saves 2.6 turns/yr for 0.75pp/yr [V].
- **Deferred book alone (hold rule), fit / H13 [V]:**
  - gross SR 0.66 / 1.81
  - ann 3.16 / 9.85%
  - maxDD −12.8 / −5.0%
  - BE 45.4 / 23.4bp
- **Cross-check.** A separately written loop, in the leakage report's `parity.py` form, gives an identical deferred book (max difference 0.0) [V]. The reviewer confirmed the deferral matches `decide.py:332-342`.
- This is a report, not a trial; no significance bar applies.

## (3) Fill drag [U]

Drag is 5.5bp [V parent] × turnover.

| turnover basis | turn/yr | drag %/yr |
|---|---:|---:|
| fit, hold / flatten | 7.2 / 8.5 | 0.39 / 0.47 |
| 2020-22, hold / flatten | 21.5 / 24.2 | 1.18 / 1.33 |
| H13, instant | 44.7 | 2.46 |
| H13, deferred | 42.1 | 2.31 |
| live window, all trading | 58.7 | 3.23 |
| live window, without the build | 43.6 | 2.40 |

- **H13 after drag (hold book).** Net SR is 1.50 instant and 1.39 deferred [U].
- **Fit under the flatten replica.** The drag of 0.47%/yr is 30% of the 1.58%/yr gross [U].

## Context only: other frontier widths, same ceiling, hold book, nothing chosen [V]

| width | fit turn/yr | H13 turn/yr |
|---|---:|---:|
| 2.4% | 10.2 | 59.3 |
| 3.2% | 9.0 | 53.5 |
| **4.8% (live)** | 7.2 | 44.7 |
| 6.4% | 5.9 | 38.0 |
| 9.6% | 4.3 | 28.5 |

- The fit column includes the empty 2005-09 era, so the fit-to-H13 ratio overstates the rise. The first pass's "about 6× at every width" is withdrawn.
- `run.log` has all ten widths with gross SR.

## Review findings and disposition
1. **Fit and era rows scored the hold rule, not the live flatten rule.**
   - Confirmed: I re-ran the reviewer's `rv2.py` and `rv3.py` and got the same figures.
   - Disposition: the warning at the top, the flatten rows, and a rewritten Answer 3.
2. **"About six times" was inflated by the empty 2005-09 era.**
   - Confirmed.
   - Disposition: restated by era (2.1× hold, 1.8× flatten).
3. **DIST_END was the latest ex-date across all names.**
   - On this panel the cut is sound [V].
   - The per-name assertion of the next ex-date is not yet in `turnover_live.py` (F4).
4. **The sign-flip flag ignored the gross sign.**
   - No row here triggers it. Every "YES" above was read off the net columns, and every gross figure is positive.
   - The fix is F5.

## Not modelled
- **The live sleeve's other eligibility drops** (stale-NAV gate, missing-NAV hold). The flatten replica counts only z and ADV, so it probably understates the live sleeve's flat days [U].
- **Share drift.** The live band compares against held shares at today's price; the harness holds constant weights.
- **`min_abs_weight` re-neutralisation and whole-share sizing.**
- **The opening session's build** is handled only as arithmetic. The flatten replica's re-entries after thin stretches are builds too, and they are inside its turnover.
- **The deferred flip on the flatten book.**

## Harness change (uncommitted, on this branch)
- **`defer_flips` option.** `scripts/cef/band_frontier.py::band_gross_capped` gains `defer_flips=False`.
  - The default output is unchanged; hashes match before and after the edit. With the ceiling: `173f767e…2432`. With `cap=inf`: `2c205883…70cc`, which equals `band(T, BAND_WIDTH)`.
  - The re-derivation also found `DataFrame.equals` True against HEAD [V].
- **New tests.** `scripts/cef/tests/test_band_defer_flips.py` has four tests.
  - Two fail when the deferral is removed; the other two hold by construction.
  - The reviewer confirmed this.
- **Full suite.** `python3 -m pytest` passes (exit 0).
- **No flatten option yet.** The harness has no flatten-on-thin option. The flatten rows come from a scratchpad replica, not from a harness change.

## Reproduce

From the worktree root, about 4s each:
```
python3 results/backtests/turnover-live-2026-11-02/turnover_live.py   # hold-book tables -> run.log, results.json
python3 results/backtests/turnover-live-2026-11-02/crosscheck.py      # second method -> crosscheck.log
python3 -m pytest scripts/cef/tests/test_band_defer_flips.py
python3 results/backtests/turnover-live-2026-11-02/flatten_replica.py   # hold vs flatten replica, cost grid
python3 results/backtests/turnover-live-2026-11-02/thin_day_split.py    # thin-day split of the hold-book P&L
```
The two replica scripts were moved here from the session scratchpad on 2026-11-02 and re-run from the worktree: they reproduce the FIT and H13 rows above. F3 (a `below_min_names` harness option with a no-op proof, and a second method) is still open.

Files (paths from the repository root):
- `results/backtests/turnover-live-2026-11-02/turnover_live.py`
- `results/backtests/turnover-live-2026-11-02/crosscheck.py`
- `results/backtests/turnover-live-2026-11-02/run.log`
- `results/backtests/turnover-live-2026-11-02/crosscheck.log`
- `results/backtests/turnover-live-2026-11-02/results.json`
- `scripts/cef/band_frontier.py` (modified)
- `scripts/cef/tests/test_band_defer_flips.py` (new)

## Follow-ups (workflow side; no team-lead decision needed)
- **F1** (parent session; needs the fills): compare live and harness turnover per session for decisions 09-28..10-14, especially 10-05 and 10-06.
- **F2** (parent session): does the $558,927 include the opening build, and at what gross did the live book open?
- **F3:** move the flatten work into the repo and re-run on it.
  - Move the flatten replica into the results folder.
  - Add a `below_min_names` option to `band_gross_capped`, off by default, with a byte-for-byte no-op proof as for `defer_flips`.
  - Re-run the deferred-flip table (fit, A2) on the flatten book.
  - Cross-check the flatten rows with a second method.
- **F4:** assert per name that each name's next expected ex-date falls after DIST_END.
- **F5:** make the sign-flip flag compare the gross sign too.

## Open questions for the team lead
1. **Which thin-day rule should the reference book use for live comparisons and the real-money cost case?**
   - On the harness's hold rule, fit break-even is 45.8bp.
   - On a replica of the live flatten rule, it is 18.6bp, and the fit-era net return is −0.97%/yr at 30bp [V, replica].
   - That choice decides how the cost story reads: "the cost case deteriorated in H13", or "the fit-era cost case was never as strong as reported".
   - Separately, should the live rule move from flatten to `hold`? That is a spec decision, made through `/spec-change`.
2. **Is the 4.8% band's cost case strong enough for real capital?**
   - Under the live rule the net sign flips at 30bp in every era, and at 15bp in 2010-14 and 2015-19.
   - H13 break-even is 23.8bp [V, replica].
   - Which era and which cost level should the real-money case be judged on?
   - Should the ceiling-driven turnover in 2023+ (at most 38%) be a pre-registered study of its own?
3. **Deferred flips on paper.** Should the deferral stay on paper under `late_market`? The alternative is to send the opening leg once the closing leg's market `day` order has filled.
   - The deferral exists only because a `cls` close cannot be confirmed before the auction.
   - On the hold book it costs −0.75pp/yr in H13 and saves 2.6 turns/yr [V].
   - Its fit cost under the live rule is not yet measured.
4. **Opening build.** Should quoted live turnover exclude it? It is 58.7/yr with the build and 43.6/yr without [U].
5. **Panel refresh.** Distributions end 2026-09-03; prices and NAV end 2026-10-15 and 2026-10-14. A refresh writes `data/`, which is an ops action outside this task.
6. **Harness default.** Once F3 adds the flatten option, should `harness.report`'s "live policy" default to the live flatten rule?
   - The no-op proof keeps today's default.
   - Changing the default moves every fit-era figure that cites the harness's live policy.