# Thin sessions, a third rule: trade the eligible names (final report, 2026-11-03)

Written to disk by the main session from the workflow's final report (the subagent's file tool refused report files), 2026-11-03. The code and data it cites are committed on `research-thin-third-rule` at 0a8795a.

**Report only. Zero trials, no spec change, no edit to the live path, nothing chosen, no pre-registration drafted.** Branch `research-thin-third-rule`. The CEF counter is not moved.

This report follows two things:
- PR #33 (`results/backtests/thin-days-2026-11-03/REPORT.md`), which compared "hold" against "flatten";
- the team lead's request of 2026-11-02 to screen a third rule. On a session with fewer than `min_names` eligible names, the third rule trades the eligible names with the sleeve's own construction. The harness default holds a frozen book instead, and the live sleeve goes flat.

How the build was checked:
- Two independent passes checked the first build (5b4b2d3): a review and a beta-detector pass.
- Their findings were fixed, and their attacks re-run on committed code, in f5a5b9e.
- A finishing pass (0a8795a) derived the factor regression's Dimson lag and wrote this report.
- §9 lists every defect and what was done about it.

**Labels.**
- [V]: computed in this workflow by the committed script named, on the repo panels.
- [S]: quoted from the document or pass named, not re-run here.
- [U]: an interpretation, or arithmetic on approximate inputs.

**Panels and spec.**
- **Spec.** `cef_discount.v7.20260928`, read through `scripts/cef/spec.py`. That is the spec on this branch and on `main`.
- **Prod.** The task context says prod runs `release-20261102-1`, ARMED. That tag carries v8: CEF trial 53, `sizing_multiplier` 1.13 on the core [S: task context].
  - **Which tag prod runs is not measured here**, because this task may not reach the VM.
  - `third_rule.py` reads that tag's frozen spec with `git show`: `cef_discount.v8.20261101`, m = 1.13 [V]. It uses it only in §7's expected-effect rows.
- **Price and NAV panels.** These are PR #33's. Prices end 2026-10-15 and NAV 2026-10-14, so the targets end **2026-10-14**.
- **Return cut.** Universe distributions end 2026-09-03, so **every return is cut at DIST_END = 2026-09-03**. PR #33's `thin_days.load` asserts the cut.
- **Other panels.**
  - ETF panel (`data/rv/etf_panel.parquet`, used only by the factor regression): to 2026-10-09.
  - IBKR fee panel: 2021-09-13 to 2026-09-09.
- **Staleness.** All panels are three to seven weeks stale against today, 2026-11-03. `data/` was read, never written: no file under it is newer than the run [V].

**The rules compared.** All run on the canonical path: `build_targets` → `band_gross_capped` → `evaluate`, with shift(2) (decide t, fill t+1, earn t+2) and total returns.

| rule | on a session with fewer than `min_names` (6) eligible names |
|---|---|
| hold | the harness default: carry the previous target; band and ceiling as usual |
| flatten | **the live sleeve**: every name FLAT; the band reopens from zero at the edge |
| **te4** | **the third rule:** with 4 or 5 eligible names, build the target on those names with the sleeve's construction, then band and ceiling as usual; with fewer than 4, FLAT as the live sleeve does |
| te3, te5 | the same rule at the floors either side of 4 (plateau check only) |

---

## The answer

### 1. Which rule scored higher

**On gross return, te4 scored highest in every window and with both flip modes** [V, `third_rule.py` → `tables.py` A]. Gross is the paper account's own score (D19/D20: no borrow, no execution cost).

| window | hold | flatten (live) | te4 |
|---|---:|---:|---:|
| 2010-14 | 2.24 / 2.25 | 0.69 / 0.73 | **4.98 / 4.71** |
| 2015-19 | 5.70 / 5.62 | 0.95 / 0.86 | **8.14 / 6.98** |
| 2020-22 | 6.49 / 5.84 | 6.73 / 6.12 | **12.76 / 12.64** |
| FIT <2023 | 3.29 / 3.16 | 1.58 / 1.46 | **5.77 / 5.35** |
| H13 2023+ | 10.61 / 9.85 | 10.63 / 10.34 | **11.50 / 10.95** |

Figures are gross ann %, instant flips / deferred flips; the live runner defers flips. In 2005-09 no rule holds anything, because no session had more than 3 eligible names.

**Net of the cost grid** (the real-money view, with no borrow) [V, `tables.py` B, D]:
- **Against flatten:** te4 stays ahead over the fit period at 5, 15 and 30bp (+3.65 / +2.58 / +0.96pp/yr). In 2015-19 it falls behind at 30bp (−1.98), because it trades four and a half times as much there.
- **Against hold:** hold is ahead over the fit period at 30bp (te4 −0.01 against hold +1.13), and in 2015-19 from 15bp.
- **H13:** te4 is ahead of both at 5 and 15bp. At 30bp every rule is negative.

**Net of borrow, where borrow is measured.** This applies to real money only; paper charges no borrow. [V, `bf.borrow_charge` on the IBKR fee panel; `tables.py` J]

| measured window | te4 − flatten, gross → net | te4 − hold, gross → net |
|---|---|---|
| 2021-09-14 to 2022-12-30 | +7.72 → **+2.79** | +6.69 → +7.51 |
| 2023-01-03 to DIST_END | +0.87 → **−2.33** | +0.90 → −0.12 |

**Not every metric favours te4:**
- Flatten has the shallowest drawdown in every window from 2015 on.
- Flatten has the best Sharpe ratio on H13: 2.07, against te4's 2.01 and hold's 1.95 (instant).

### 2. Did te4's edge over flatten survive the attack as alpha? No

**It is real gross P&L on this panel, and its sign follows the signal.** Every attack on its nature failed to remove it (§6):
- **Not factor beta.** With the Dimson lag derived (K = 2), alpha is +6.26pp/yr (t 4.41), and every fit-period beta is 0.06 or less in absolute value.
- **Not a stale price.** It survives one extra session of delay: +3.06 (t 3.62).
- **Not distributions.** The thin-day P&L is in the price leg: +4.22 of the +3.94, with the distribution leg at −0.28.
- **Not a standing tilt.** Half the thin-day P&L is gone when the signal is 5 sessions old, and an in-sample static tilt loses money (−1.63).
- **The direction matters.** None of 500 random within-session reassignments reached it (p < 0.002).

**But it is not shown to be alpha, for six reasons** [V unless marked]:
1. **At matched turnover (H2, the repo's rule) it is under the bar.**
   - te4 trades 2.3 times flatten's fit turnover (19.3 against 8.5/yr).
   - Re-banded to flatten's turnover (the device declared before the first run), the gap is **+2.13pp/yr, NW t 2.34**. That is under the bar of 2.818 at N = 53.
   - `read_result` reads **INCONCLUSIVE**, interval [−0.87, +5.14].
   - About half of the unmatched +4.19 is extra trading. The unmatched reading (t 4.51, PRESENT) is not an H2 comparison.
2. **It is two names and one sponsor.**
   - Take PHK's and PDI's own P&L out, and the fit gap is +1.08 (t 1.43).
   - The six PIMCO funds carry +3.63 of the +4.19pp/yr (t 3.64). The other seven names carry +0.56.
   - A universe rebuilt without PHK and PDI gives +2.23 (t 3.55). That is a different book: it is thin on 4,800 sessions, and its edge comes from 2020-22 (t 0.90 in 2015-19).
   - The two methods disagree, and both are shown.
3. **Counted as independent episodes, it misses the bar.**
   - Merging stretches fewer than 63 sessions apart (the ADV window) turns the 24 fit stretches into 9 episodes.
   - All 9 are positive. Their t is 3.68, against a small-sample critical value of 3.86 at N = 53: a miss.
   - The exact sign test passes by a hair (p 0.0020 against 0.00242).
4. **On the 2023 holdout it is not shown.** The gap is +0.87pp/yr (t 0.72), from one 138-session episode (+3.02pp, positive). The direction control there gives p 0.242.
5. **Borrow takes it on real money.**
   - At measured 2023+ fees the extra shorts cost more than the gap: −2.33pp/yr net.
   - In 2021-22 borrow took 64% of the gap.
   - The signal shorts rich PIMCO funds when they are expensive to borrow.
   - Before 2021-09-13 borrow is unmeasured.
6. **It cannot be tested forward with adequate power.**
   - At the fit effect, a pre-registered test needs about 5 new independent episodes for a coin-flip pass (P 0.47; P 0.07 at the holdout's shrunk effect).
   - That is 7 years at the fit period's rate, and 18 at the rate since 2023.
   - There has been no thin session since 2023-08-30.

**One question these files cannot answer.** **77% of fit-period earning days (3,484 of 4,531) follow a thin decision.** Those thin sessions exist because the 2026 universe is projected back into years when most of it was illiquid. te4's whole edge is earned there, and these files cannot measure the hindsight in that universe.

**Against hold, te4's edge is not robust either:**
- unmatched, the fit gap is +2.48 (t 3.03);
- **at matched turnover it is −0.26 (t −0.30)**;
- `read_result` reads INCONCLUSIVE at every N;
- without its best 10 days the t is 1.68;
- 8 of 9 episodes are positive with t 3.23, but both the t-test and the sign test fail.

### 3. The expected effect on the CURRENT book going forward [U]

The current book is the m = 1.13 book of `release-20261102-1`, if prod runs that tag [S: task context]. §7 has the arithmetic.
- **Now: zero.** No session has been thin since 2023-08-30: 783 sessions up to 2026-10-14. With 6 or more eligible names, all three rules build the same target.
- **If thin sessions recur at 2023's share (15% of sessions):**
  - **On the out-of-sample analogue (2023+ itself):** about **+0.84pp/yr gross** at m. On real money it is about **−2.9pp/yr net**, after extra turnover at 15bp (0.44) and extra borrow at 2023+ fees (3.29).
  - **On the fit period's per-session edge:** about +1.97pp/yr gross at m, and −2.1 net. The fit edge per session is about twice the holdout's, so this is the optimistic row.
- **How close the book runs to thin.** On the 406 sessions since 2023 with 6 or 7 eligible names, the least liquid eligible name's ADV sat at a median 1.13 times the $3m floor (p10 1.03). One ADV dip makes every thin rule live again.

### 4. What follows

**No pre-registration is drafted** (§8). Nothing is chosen here. The rule choice belongs to the team lead, whose standing ruling of 2026-11-02 keeps flatten live. On this panel te4 is the highest-return rule. But its edge over flatten is not shown to be alpha, and a forward test would take years.

---

## 1. The floor, derived before any scoring run

**Order.** The derivation below was written into the harness's docstrings (`_min_names_arg` and `band_gross_capped`) after the no-op proof and before the first scoring run. The first build is a single commit, so git cannot show that order. The plateau is read on the fit period only; nothing is taken from 2023+.

**The construction.** This is `src/deploy/sleeves/cef_discount.py::target_positions` l.911-920, and the harness's `_target_row`, moved verbatim out of `build_targets`. On the n eligible names:

w_i = −(z_i − z̄) / Σ_j |z_j − z̄|, then times clip(0.06 / rv, 0.2, 2.5),

where rv is the annualised volatility of the book's own trailing 63 sessions. Before the scalar, Σw = 0 and Σ|w| = 1, so the longs sum to ½ and the shorts to ½.

| n | what the construction does | breaks? |
|---|---|---|
| 1 | z − z̄ = 0, so w = 0/0 = NaN. `build_targets` would fill it with 0 on a session it calls active, which is a silent book. `_min_names_arg` refuses `min_names` < 2 | **yes: undefined** |
| 2 | w = ±½ whatever \|z₁ − z₂\| is. The weights carry only the sign of z₁ − z₂, and each crossing reverses the whole book. The magnitude the sizing relies on is discarded | **yes: sign only** |
| 3 | The demeaned values sum to zero, so one side holds exactly one fund carrying ½ of the gross (unless a z sits exactly at the mean) | **yes: a forced single-fund side** |
| 4 | A 2–2 split is possible. On te4's traded sessions a single-fund side occurred on 27.3% of 4-name sessions and 16.0% of 5-name sessions [V]: possible, not forced | no |

Test 3 of `scripts/cef/tests/test_band_trade_eligible.py` pins the facts for n = 2 and n = 3.

**What does not break at any n ≥ 2:**
- each fund's z-score against its own history (l.756-758);
- dollar neutrality;
- the vol scalar: a concentrated book is more volatile, so the scalar shrinks it;
- the gross ceiling, which is one uniform scale-down.

All z-scores equal gives 0/0 at any n. No te4 session with 4 or 5 eligible names had it [V].

**One part depends on `min_names` itself: the min-weight block.** The re-neutralisation after the 0.005 filter (l.926-933) runs only if `len(keep) >= min_names`. On a reduced set it therefore never runs, as the code stands. A live version of the rule would have to decide that guard.

**Floor = 4**: the smallest count with none of the three degeneracies. The plateau is checked at 3 and 5. Below the floor the rule does what the live sleeve does: FLAT.

## 2. The harness option, its no-op proof and its tests

All changes are in `scripts/cef/band_frontier.py`. None touches `src/deploy/`, `quantt/` or `ops/specs/`.

| change | what it does |
|---|---|
| `build_targets(..., min_names=None)` | None means the spec's `min_names`, read at call time; the default path is unchanged. An int ≥ 2 builds the target on the smaller eligible set with the unchanged construction |
| `thin_sessions(..., min_names=None)` | None is unchanged: a Series named "thin". An int counts against that floor and names the Series "thin_below_<n>" |
| `_target_row(row, ret, i)` | `build_targets`' construction lines, moved out verbatim so that the placebo and §7's hypothetical use the one definition |
| `band_gross_capped(..., below_min_names="trade_eligible", thin=, floor=)` | `floor` must be an int with 2 ≤ floor < `min_names`. `thin` must be named "thin_below_<floor>". T and the mask must agree (`_check_thin_matches_T`, PR #33's guard). A below-floor row is zero; every other row is the unchanged loop. `floor` is refused under "hold" and "flatten" |

**The defaults are byte-identical** [V]. `noop_hash.py` hashes eleven default-path objects: PR #33's eight, `thin_sessions(T.index)`, and the two "flatten" books.
- Its output is the same before the edit (`noop_before.txt`) and after both the edit and the `_target_row` refactor (`noop_after.txt`).
- The first eight hashes equal PR #33's `noop_after.txt`, so the panel has not moved since that report.
- The review reproduced all eleven [S: review pass].

**Tests** (`scripts/cef/tests/test_band_trade_eligible.py`, synthetic panels, 7 tests):
1. The defaults are unchanged.
2. On a reduced session the target equals an independent numpy copy of the sleeve's construction. With 6 or more eligible names it equals the default target exactly. Below the floor it repeats the previous row.
3. The derivation's facts for n = 2 and n = 3.
4. The book is FLAT below the floor, trades between the floor and `min_names`, and equals an independent loop: ceiling on and off, instant and deferred flips.
5. "trade_eligible" and "flatten" run the same loop given the same mask.
6. Every argument mismatch raises.
7. **The gross ceiling binds under "trade_eligible"** on reduced-set sessions. This test was added after the review. Quiet synthetic returns push the vol scalar to its clip, so the target passes the ceiling.

**Mutation checks.** Each mutation was applied to `band_frontier.py`, the tests run, and the file restored:

| mutation | tests that fail |
|---|---|
| option removed from `BELOW_MIN_NAMES` | 4, 5, 6 |
| `build_targets` ignores `min_names` | 2, 3, 4, 5, 6 |
| below-floor row banded, not zeroed | 4, 5 |
| `thin_sessions` ignores `min_names` | 1, 4, 5, 6 |
| mask-name check removed | 6 |
| `min_names` = 1 accepted | 6 |
| ceiling skipped under "trade_eligible" (the review's N3) | **7** (both flip modes) |
| ceiling doubled under "trade_eligible" (the review's N12) | **7** (both flip modes) |

- The first six rows are the first build's record [S: 5b4b2d3].
- N3 and N12 survived every test at 5b4b2d3 [S: review]. This pass re-applied both to a scratch copy of the committed code, and both now fail test 7 [V].
- PR #33's tests pass under every mutation.
- **`python3 -m pytest` exits 0** [V].

**Second methods.** Each is asserted on every run of `third_rule.py` [V]:
- **The live sleeve.** `sleeve_reduced_check.py` calls `CEFDiscountSleeve.target_positions` on all 3,622 thin sessions, using a deep copy of the spec with `min_names` lowered to 3 in memory.
  - It is below the floor on exactly the 1,565 sessions with fewer than 3 eligible names.
  - On the 1,917 traded sessions with no eligible weight under `min_abs_weight`, its target after the ceiling equals the harness's to 5.6e-16.
  - On the other 140 its min-weight block acts. At floor 4 that is 127 sessions: 18 with 4 names and 109 with 5. The largest weight difference is 0.0050.
  - The sleeve reads its panel only up to each decision date, so this also rules out lookahead in the z-score, the ADV and the vol scalar [S: review].
- **An independent loop.** PR #33's `independent_flatten`, given each floor's targets and mask, reproduces every te book to ≤ 1e-12.
- **`harness.report`** (`nan_policy="raise"`) reproduces te4's fit and holdout Sharpe ratios (1.201 and 2.013).

**Reproducibility.** The finishing pass re-ran `third_rule.py`. `results.json` is identical to f5a5b9e's in every field except the factor-regression rows. Those were renamed for the derived lag, and their values are identical (§6, L) [V].

## 3. Scores: by era, fit and H13, both flip modes

**How the rows are computed:**
- Total returns, shift(2). These are v7 unit-sized books.
- Turnover is Σ|ΔH| × 252 / n.
- Net = ann − turn × c. This is the real-money view, labelled as such. **No borrow is charged** (§5).
- BE = ann / turn, in bp.
- "Sign flips at" is the first grid cost at which net and gross have opposite signs.
- Vol-matched scales each book to 6% on its own ex-post vol in the window. It is descriptive only.

All figures are [V], `tables.py` B.

| window | rule | flips | SR | ann % | vol % | maxDD % | turn/yr | net %/yr @5 / @15 / @30 | BE bp | sign flips at | vol-matched ann % (net @15) |
|---|---|---|---:|---:|---:|---:|---:|---|---:|---|---|
| 2005-09 | all | both | flat: nothing held | | | | 0.0 | | | | |
| 2010-14 | hold | instant | 0.72 | 2.24 | 3.12 | -4.5 | 5.2 | 1.98 / 1.46 / 0.69 | 43.3 | no | 4.30 (2.81) |
| 2010-14 | hold | deferred | 0.72 | 2.25 | 3.12 | -4.5 | 5.0 | 2.00 / 1.50 / 0.75 | 44.9 | no | 4.32 (2.88) |
| 2010-14 | flatten | instant | 0.29 | 0.69 | 2.40 | -5.2 | 7.3 | 0.33 / -0.40 / -1.50 | 9.5 | 15bp | 1.73 (-1.01) |
| 2010-14 | flatten | deferred | 0.30 | 0.73 | 2.40 | -5.2 | 7.2 | 0.37 / -0.35 / -1.42 | 10.2 | 15bp | 1.82 (-0.87) |
| 2010-14 | te4 | instant | 1.33 | 4.98 | 3.74 | -4.5 | 11.6 | 4.40 / 3.24 / 1.50 | 42.9 | no | 7.98 (5.19) |
| 2010-14 | te4 | deferred | 1.27 | 4.71 | 3.71 | -4.5 | 11.0 | 4.16 / 3.05 / 1.40 | 42.7 | no | 7.61 (4.94) |
| 2015-19 | hold | instant | 0.84 | 5.70 | 6.83 | -12.8 | 7.8 | 5.31 / 4.53 / 3.36 | 73.2 | no | 5.01 (3.98) |
| 2015-19 | hold | deferred | 0.82 | 5.62 | 6.83 | -12.8 | 7.6 | 5.24 / 4.48 / 3.34 | 74.0 | no | 4.93 (3.93) |
| 2015-19 | flatten | instant | 0.38 | 0.95 | 2.48 | -6.6 | 8.7 | 0.51 / -0.36 / -1.68 | 10.8 | 15bp | 2.29 (-0.88) |
| 2015-19 | flatten | deferred | 0.35 | 0.86 | 2.48 | -6.8 | 8.6 | 0.43 / -0.44 / -1.73 | 9.9 | 15bp | 2.08 (-1.06) |
| 2015-19 | te4 | instant | 1.24 | 8.14 | 6.57 | -11.2 | 39.3 | 6.17 / 2.24 / -3.66 | 20.7 | 30bp | 7.43 (2.04) |
| 2015-19 | te4 | deferred | 1.06 | 6.98 | 6.56 | -11.6 | 37.3 | 5.12 / 1.39 / -4.20 | 18.7 | 30bp | 6.39 (1.27) |
| 2020-22 | hold | instant | 1.02 | 6.49 | 6.36 | -4.3 | 21.5 | 5.41 / 3.27 / 0.05 | 30.2 | no | 6.12 (3.09) |
| 2020-22 | hold | deferred | 0.90 | 5.84 | 6.52 | -4.3 | 20.7 | 4.80 / 2.74 / -0.37 | 28.2 | 30bp | 5.37 (2.52) |
| 2020-22 | flatten | instant | 1.37 | 6.73 | 4.92 | -3.5 | 24.2 | 5.52 / 3.10 / -0.52 | 27.8 | 30bp | 8.20 (3.78) |
| 2020-22 | flatten | deferred | 1.19 | 6.12 | 5.15 | -3.7 | 23.4 | 4.96 / 2.62 / -0.89 | 26.2 | 30bp | 7.14 (3.05) |
| 2020-22 | te4 | instant | 1.95 | 12.76 | 6.54 | -3.6 | 30.7 | 11.22 / 8.15 / 3.54 | 41.5 | no | 11.70 (7.47) |
| 2020-22 | te4 | deferred | 1.90 | 12.64 | 6.67 | -3.8 | 29.6 | 11.15 / 8.19 / 3.75 | 42.7 | no | 11.37 (7.37) |
| FIT <2023 | hold | instant | 0.69 | 3.29 | 4.73 | -12.8 | 7.2 | 2.93 / 2.21 / 1.13 | 45.8 | no | 4.17 (2.80) |
| FIT <2023 | hold | deferred | 0.66 | 3.16 | 4.77 | -12.8 | 7.0 | 2.81 / 2.12 / 1.07 | 45.4 | no | 3.97 (2.66) |
| FIT <2023 | flatten | instant | 0.58 | 1.58 | 2.72 | -6.6 | 8.5 | 1.15 / 0.30 / -0.97 | 18.6 | 30bp | 3.49 (0.67) |
| FIT <2023 | flatten | deferred (live rule) | 0.53 | 1.46 | 2.78 | -6.8 | 8.3 | 1.05 / 0.22 / -1.02 | 17.6 | 30bp | 3.15 (0.47) |
| FIT <2023 | te4 | instant | 1.20 | 5.77 | 4.81 | -11.2 | 19.3 | 4.81 / 2.88 / -0.01 | 29.9 | 30bp | 7.20 (3.60) |
| FIT <2023 | te4 | deferred | 1.11 | 5.35 | 4.82 | -11.6 | 18.4 | 4.44 / 2.60 / -0.15 | 29.2 | 30bp | 6.66 (3.24) |
| H13 2023+ | hold | instant | 1.95 | 10.61 | 5.43 | -4.9 | 44.7 | 8.37 / 3.91 / -2.79 | 23.8 | 30bp | 11.71 (4.32) |
| H13 2023+ | hold | deferred | 1.81 | 9.85 | 5.44 | -5.0 | 42.1 | 7.75 / 3.55 / -2.76 | 23.4 | 30bp | 10.87 (3.91) |
| H13 2023+ | flatten | instant | 2.07 | 10.63 | 5.13 | -2.9 | 44.7 | 8.39 / 3.92 / -2.79 | 23.8 | 30bp | 12.43 (4.59) |
| H13 2023+ | flatten | deferred (live rule) | 2.02 | 10.34 | 5.11 | -3.2 | 42.2 | 8.23 / 4.00 / -2.34 | 24.5 | 30bp | 12.14 (4.70) |
| H13 2023+ | te4 | instant | 2.01 | 11.50 | 5.71 | -3.1 | 47.3 | 9.13 / 4.40 / -2.70 | 24.3 | 30bp | 12.08 (4.62) |
| H13 2023+ | te4 | deferred | 1.92 | 10.95 | 5.71 | -3.2 | 44.7 | 8.72 / 4.25 / -2.45 | 24.5 | 30bp | 11.50 (4.46) |
| full | hold | instant | 0.93 | 4.52 | 4.86 | -12.8 | 13.5 | 3.85 / 2.50 / 0.47 | 33.5 | no | 5.58 (3.08) |
| full | flatten | instant | 0.95 | 3.11 | 3.26 | -6.6 | 14.6 | 2.38 / 0.92 / -1.28 | 21.3 | 30bp | 5.72 (1.69) |
| full | te4 | instant | 1.36 | 6.74 | 4.97 | -11.2 | 24.0 | 5.54 / 3.14 / -0.46 | 28.1 | 30bp | 8.13 (3.79) |

The hold and flatten rows equal PR #33's §3 to the digit. The full-sample deferred rows are in `results.json` under "table".

**The leading rule by metric**, instant / deferred [V, `tables.py` A2]:

| window | gross ann | SR | net @5 | net @15 | net @30 | maxDD (shallowest) | vol-matched ann |
|---|---|---|---|---|---|---|---|
| 2010-14 | te4 / te4 | te4 / te4 | te4 / te4 | te4 / te4 | te4 / te4 | hold / te4 (−4.5 each) | te4 / te4 |
| 2015-19 | te4 / te4 | te4 / te4 | te4 / hold | hold / hold | hold / hold | flatten / flatten | te4 / te4 |
| 2020-22 | te4 / te4 | te4 / te4 | te4 / te4 | te4 / te4 | te4 / te4 | flatten / flatten | te4 / te4 |
| FIT <2023 | te4 / te4 | te4 / te4 | te4 / te4 | te4 / te4 | hold / hold | flatten / flatten | te4 / te4 |
| H13 2023+ | te4 / te4 | flatten / flatten | te4 / te4 | te4 / te4 | te4 / flatten | flatten / flatten | flatten / flatten |

**Paired daily difference, te4 minus each rule**, pp/yr (NW t, Newey-West 1994 lag) [V, `tables.py` C]

| window | − flatten, instant | − flatten, deferred | − hold, instant | − hold, deferred |
|---|---|---|---|---|
| 2010-14 | +4.28 (3.05) | +3.98 (2.96) | +2.74 (2.28) | +2.46 (2.00) |
| 2015-19 | +7.19 (2.63) | +6.12 (2.34) | +2.44 (0.97) | +1.37 (0.56) |
| 2020-22 | +6.03 (2.61) | +6.51 (2.74) | +6.27 (3.05) | +6.80 (3.07) |
| FIT <2023 | +4.19 (4.51) | +3.89 (4.33) | +2.48 (3.03) | +2.20 (2.68) |
| H13 2023+ | +0.87 (0.72) | +0.61 (0.48) | +0.90 (0.98) | +1.09 (1.23) |
| full | +3.63 (4.54) | +3.34 (4.29) | +2.21 (3.17) | +2.01 (2.89) |

These gaps are **not turnover-matched** in the fit period (see H2 below). They are the unmatched, descriptive gaps.

**The gap after the cost grid** (instant), and whether its sign flips [V, `tables.py` D]

| window | vs | gross | @5 | @15 | @30 | sign flips? |
|---|---|---:|---:|---:|---:|---|
| 2010-14 | flatten | +4.28 | +4.07 | +3.64 | +3.00 | no |
| 2010-14 | hold | +2.74 | +2.42 | +1.77 | +0.81 | no |
| 2015-19 | flatten | +7.19 | +5.66 | +2.60 | −1.98 | **yes, 30bp** |
| 2015-19 | hold | +2.44 | +0.86 | −2.29 | −7.02 | **yes, 15bp** |
| 2020-22 | flatten | +6.03 | +5.70 | +5.05 | +4.06 | no |
| 2020-22 | hold | +6.27 | +5.81 | +4.88 | +3.49 | no |
| FIT <2023 | flatten | +4.19 | +3.65 | +2.58 | +0.96 | no |
| FIT <2023 | hold | +2.48 | +1.88 | +0.67 | −1.14 | **yes, 30bp** |
| H13 2023+ | flatten | +0.87 | +0.74 | +0.48 | +0.09 | no |
| H13 2023+ | hold | +0.90 | +0.76 | +0.49 | +0.09 | no |

**Gross on thin-decision earning days and on active ones**, ann % of the window, instant / deferred [V, `tables.py` E]

| window | thin earning days | hold thin | hold active | flatten thin | flatten active | te4 thin | te4 active |
|---|---:|---|---|---|---|---|---|
| 2010-14 | 985 | 1.45 / 1.45 | 0.79 / 0.80 | 0.00 / 0.00 | 0.69 / 0.73 | 4.12 / 3.81 | 0.86 / 0.89 |
| 2015-19 | 906 | 3.99 / 4.01 | 1.71 / 1.61 | 0.00 / 0.00 | 0.95 / 0.86 | 6.70 / 5.60 | 1.44 / 1.38 |
| 2020-22 | 336 | -0.60 / -0.49 | 7.09 / 6.33 | 0.00 / 0.00 | 6.73 / 6.12 | 5.60 / 6.13 | 7.16 / 6.51 |
| FIT <2023 | 3484 | 1.41 / 1.43 | 1.88 / 1.73 | 0.00 / 0.00 | 1.58 / 1.46 | 3.94 / 3.64 | 1.83 / 1.72 |
| H13 2023+ | 138 | -0.02 / -0.00 | 10.62 / 9.86 | 0.00 / 0.00 | 10.63 / 10.34 | 0.83 / 0.91 | 10.67 / 10.04 |
| full | 3622 | 1.17 / 1.19 | 3.36 / 3.10 | 0.00 / 0.00 | 3.11 / 2.96 | 3.41 / 3.18 | 3.33 / 3.12 |

Most of te4's fit gap over flatten is P&L on thin days: 3.94 of the 4.19pp/yr. The other +0.25 comes on active days. te4 never goes to zero, so it does not pay flatten's re-entry at the band edge.

**Turnover (H2)** [V, `tables.py` F]

| window | hold | flatten | te4 | te4 vs flatten | te4 vs hold |
|---|---:|---:|---:|---:|---:|
| 2010-14 | 5.2 | 7.3 | 11.6 | +59% | +125% |
| 2015-19 | 7.8 | 8.7 | 39.3 | +350% | +405% |
| 2020-22 | 21.5 | 24.2 | 30.7 | +27% | +43% |
| FIT <2023 | 7.2 | 8.5 | 19.3 | **+127%** | **+168%** |
| H13 2023+ | 44.7 | 44.7 | 47.3 | +6% | +6% |
| full | 13.5 | 14.6 | 24.0 | +64% | +78% |

Era turnover sd/mean (H5, instant, over the eras each rule traded):
- hold 0.91, flatten 0.82 and te4 0.48, each over four eras;
- te3 0.69 over five eras, and te5 0.53 over four.

**H2: the comparison at matched fit turnover** (the review's finding 1).
- **The headline device** was declared before the first run. te4 (instant) is re-banded until its fit turnover equals the reference's. The band is found by bisection on fit turnover only, never on P&L. The widths are matching devices, not proposals.
- **The reverse direction is infeasible.** Re-banding the reference up to te4's turnover cannot get there: even at band 0, trading to the target every session, flatten turns 17.89/yr and hold 16.51/yr, against te4's 19.27. That is −7.2% and −14.3%, outside H2's 5%.
- **The reading.** `read_result` uses Šidák at N. Its `meaningful` argument is the cost hurdle: te4's extra fit turnover at the spec band × 15bp.

[V, `tables.py` F, F2]:

| matched to | te4 band | window | te4 SR / ann % / net @5, @15, @30 | ref SR / ann % / net @5, @15, @30 | gap pp/yr (NW t) | clears bar at N = 52 / 53 / 54 | `read_result` N = 53 | vs hurdle |
|---|---:|---|---|---|---|---|---|---|
| flatten | 0.1398 | **FIT (8.49 vs 8.49)** | 0.82 / 3.71 / 3.29, 2.44, 1.16 | 0.58 / 1.58 / 1.15, 0.30, −0.97 | **+2.13 (2.34)** | no / no / no | **INCONCLUSIVE [−0.87, +5.14]** | straddles 1.62 |
| hold | 0.1610 | **FIT (7.18 vs 7.18)** | 0.68 / 3.02 / 2.67, 1.95, 0.87 | 0.69 / 3.29 / 2.93, 2.21, 1.13 | **−0.26 (−0.30)** | no / no / no | INCONCLUSIVE [−3.14, +2.62] | straddles 1.81 |

**At matched fit turnover, te4 still earns more than flatten, but not significantly, and it earns less than hold.**
- **The device is crude.** It widens te4's band on every session, not only thin ones. Whether a thin-sessions-only device is the fairer H2 control is open question 5.
- **The same widths are not a match on H13.** There te4 turns 20.6 and 17.4 against 44.7. Their H13 rows (−3.73, t −2.15 against flatten; −4.79, t −2.84 against hold) show what the wide band costs a full book. They are not H2 comparisons.
- **On H13 at the spec band**, the turnovers are already within 6%.

## 4. The floor's plateau (H8)

**te3 / te4 / te5 minus each rule**, instant flips, pp/yr (NW t) [V, `tables.py` G]

| window | te3 − flatten | te4 − flatten | te5 − flatten | te3 − hold | te4 − hold | te5 − hold |
|---|---|---|---|---|---|---|
| 2005-09 | −0.26 (−0.48) | 0.00 | 0.00 | −0.26 (−0.48) | 0.00 | 0.00 |
| 2010-14 | +5.96 (3.29) | +4.28 (3.05) | +3.28 (2.90) | +4.42 (2.64) | +2.74 (2.28) | +1.74 (2.04) |
| 2015-19 | +7.19 (2.63) | +7.19 (2.63) | +5.34 (2.09) | +2.44 (0.97) | +2.44 (0.97) | +0.58 (0.24) |
| 2020-22 | +6.03 (2.61) | +6.03 (2.61) | +4.65 (2.20) | +6.27 (3.05) | +6.27 (3.05) | +4.89 (2.50) |
| FIT <2023 | +4.59 (4.61) | +4.19 (4.51) | +3.17 (3.74) | +2.88 (3.21) | +2.48 (3.03) | +1.46 (1.92) |
| H13 2023+ (not read) | +0.87 (0.72) | +0.87 (0.72) | +0.63 (0.53) | +0.90 (0.98) | +0.90 (0.98) | +0.65 (0.70) |

**Per traded session:**

| floor | thin sessions traded (all / 2005-09, 2010-14, 2015-19, 2020-22 / 2023+) | FIT share | gap per unit share vs flatten | vs hold |
|---|---|---:|---:|---:|
| 3 | 2057 / 91, 586, 908, 334 / 138 | 42.4% | +10.83 | +6.79 |
| 4 | 1708 / 0, 328, 908, 334 / 138 | 34.7% | +12.10 | +7.17 |
| 5 | 1294 / 0, 155, 706, 295 / 138 | 25.5% | +12.42 | +5.72 |

**Reading** [V for the figures, U for the reading]:
- **4 sits on a plateau.** The sign against flatten is the same at all three floors in every fit era where they differ. Per traded session the edge is nearly flat: +10.8 to +12.4pp/yr per unit share. The floor sets how many sessions are traded, not what each one earns.
- **te4 is not the fit argmax.** te3 (+4.59) is above te4 (+4.19), which is above te5 (+3.17).
- **H13 could not have steered the floor.** Since 2015 every thin session had 4 or 5 eligible names, so te3 and te4 are the same book from 2015 on, and all three floors are identical on H13.
- **4-name and 5-name sessions earn about the same per day:** +10.07 against +11.83%/yr, t 2.39 and 3.55 (§6, A to C).

## 5. Concentration, names, sponsor, borrow

**Concentration on thin sessions** (the book as decided, instant): mean / median / p90 / max [sessions] [V, `tables.py` H]

| rule | window | set | names held | max single-name \|w\| | gross |
|---|---|---|---|---|---|
| te4 | 2010-14 | thin [328] | 5.7/5.0/10.0/10.0 | 0.316/0.290/0.494/0.558 | 0.859/0.817/1.290/1.752 |
| te4 | 2015-19 | thin [908] | 10.0/10.0/10.0/10.0 | 0.453/0.456/0.671/0.844 | 1.247/1.326/1.787/1.800 |
| te4 | 2020-22 | thin [334] | 10.6/10.0/12.0/12.0 | 0.352/0.363/0.490/0.742 | 1.079/1.107/1.372/1.800 |
| te4 | FIT <2023 | thin [1570] | 9.2/10.0/10.0/12.0 | 0.403/0.388/0.633/0.844 | 1.130/1.144/1.676/1.800 |
| te4 | FIT <2023 | active [1047] | 10.2/10.0/11.0/12.0 | 0.331/0.333/0.502/0.656 | 1.173/1.213/1.621/1.800 |
| te4 | H13 2023+ | thin [138] | 12.0/12.0/12.0/12.0 | 0.384/0.383/0.443/0.488 | 1.269/1.259/1.572/1.754 |
| hold | FIT <2023 | thin [1353] | 10.0/10.0/10.0/12.0 | 0.357/0.444/0.569/0.576 | 1.225/1.324/1.800/1.800 |
| hold | H13 2023+ | thin [138] | 12.0/12.0/12.0/12.0 | 0.180/0.180/0.180/0.180 | 0.863/0.863/0.863/0.863 |

**"Names held" counts band residues.** On a 4- or 5-name session te4 holds about 10 names. The band leaves a name that is no longer eligible at its band edge (target 0, ±0.048) rather than closing it, as the live sleeve does on any active day (l.1081-1090).
- Over the fit period these residues average gross 0.056 on thin sessions. That rises to 0.126 in 2015-19 and 0.251 in H13.
- They earn +0.19 of te4's 3.94%/yr thin-day P&L (§6, A to C).
- They are names below the ADV floor, which matters for real-money capacity.

**The target itself**, on the 1,708 thin sessions te4 trades (414 with 4 names, 1,294 with 5):
- a single-fund side on 18.7% of them;
- max |w| median 0.392, p90 0.664;
- gross median 1.011;
- no 0/0 row.

**Thin books are more concentrated.** Over the fit period, max |w| p90 is 0.633 on thin sessions against 0.502 on active ones. A single name holds 0.5 of NAV or more on 27% of thin sessions, against 10% of active ones [S: beta-detector pass].

**It is not leverage.** The target gross on thin sessions (median 1.01) is lower than on active ones. The vol scalar never reaches its 2.5 clip on the real panel [S: beta-detector pass].

**Leave one name out (attribution), te4 − flatten**, instant, pp/yr (NW t). Every name is shown. The combinations are PR #33's top two for hold (PHK, PTY) and te4's own top two (PHK, PDI). [V, `tables.py` I]

| left out | 2010-14 | 2015-19 | 2020-22 | FIT <2023 | H13 2023+ |
|---|---|---|---|---|---|
| none | +4.28 (3.05) | +7.19 (2.63) | +6.03 (2.61) | +4.19 (4.51) | +0.87 (0.72) |
| **PHK** | +1.59 (1.39) | +3.48 (1.70) | +5.13 (2.27) | **+2.26 (3.06)** | +1.21 (1.07) |
| PTY | +4.41 (3.25) | +6.97 (2.72) | +5.32 (2.52) | +4.05 (4.66) | +1.17 (1.18) |
| AWF | +3.50 (2.17) | +7.53 (2.73) | +5.82 (2.46) | +4.03 (4.18) | +0.54 (0.43) |
| BIT | +4.21 (3.01) | +6.96 (2.55) | +5.80 (2.47) | +4.07 (4.37) | +0.74 (0.60) |
| DSL | +4.44 (3.09) | +6.41 (2.31) | +4.64 (1.96) | +3.79 (4.01) | +1.09 (1.02) |
| HYT | +4.30 (3.08) | +7.52 (2.61) | +7.53 (2.85) | +4.54 (4.56) | +0.54 (0.36) |
| JFR | +4.14 (2.97) | +6.89 (2.53) | +5.31 (2.30) | +3.95 (4.27) | +1.01 (0.86) |
| MHD | +4.28 (3.05) | +7.19 (2.63) | +6.03 (2.61) | +4.19 (4.51) | +0.87 (0.72) |
| MQY | +4.28 (3.05) | +7.19 (2.63) | +6.18 (2.66) | +4.22 (4.53) | +0.79 (0.62) |
| PCN | +4.18 (2.96) | +6.77 (2.47) | +6.12 (2.74) | +4.06 (4.38) | +1.10 (0.98) |
| **PDI** | +3.95 (2.91) | +5.11 (1.83) | +2.95 (1.36) | **+3.01 (3.26)** | −0.24 (−0.17) |
| PDO | +4.28 (3.05) | +7.19 (2.63) | +5.38 (2.50) | +4.08 (4.45) | +0.84 (0.77) |
| PFN | +3.83 (2.79) | +7.08 (2.59) | +6.16 (2.65) | +4.06 (4.38) | +0.78 (0.63) |
| PHK+PTY | +1.71 (1.76) | +3.26 (2.30) | +4.42 (2.16) | +2.12 (3.71) | +1.52 (1.55) |
| **PHK+PDI** | +1.26 (1.03) | +1.41 (0.67) | +2.06 (0.92) | **+1.08 (1.43)** | +0.11 (0.08) |
| PHK+PDI+PTY | +1.38 (1.31) | +1.18 (0.87) | +1.35 (0.74) | +0.94 (1.70) | +0.41 (0.42) |

The largest fit contributors are PHK (+1.93pp/yr) and PDI (+1.18). Against hold, leaving out PHK+PDI gives +0.73 (t 0.89). `tables.py` I prints the full hold table.

**Rebuilt universes.** Targets, masks and books are recomputed. A smaller universe is thin more often, so each is a different book.

| without | thin sessions | below floor 4 | FIT te4 − flatten | FIT te4 − hold | 2010-14 te4 − flatten | 2015-19 te4 − flatten | 2020-22 te4 − flatten | H13 te4 − flatten |
|---|---:|---:|---|---|---|---|---|---|
| PHK | 4175 | 2269 | +4.21 (4.99) | +4.33 (5.09) | +3.13 (2.30) | +7.74 (3.44) | +7.16 (2.97) | +1.32 (1.16) |
| PTY | 4517 | 2223 | +3.50 (3.75) | +2.13 (1.81) | +2.36 (1.76) | +6.35 (2.37) | +6.50 (2.53) | +3.84 (1.86) |
| PDI | 4517 | 2259 | +3.69 (3.57) | +2.08 (1.71) | +4.23 (2.38) | +4.56 (1.60) | +7.48 (2.80) | +2.39 (1.11) |
| PHK+PTY | 4800 | 3213 | +1.76 (2.80) | +1.93 (2.63) | +0.57 (0.53) | +0.83 (0.77) | +8.21 (2.97) | +5.10 (2.35) |
| PHK+PDI | 4800 | 3250 | +2.23 (3.55) | +2.40 (3.41) | +2.03 (1.82) | +1.00 (0.90) | +8.35 (3.11) | +3.88 (1.78) |

**The attribution and the rebuilt universe disagree on PHK+PDI** (t 1.43 against 3.55). The rebuilt book's fit edge comes from 2020-22; in 2010-14 and 2015-19 its t is 1.82 and 0.90. The two are reported side by side, not averaged (open question 6).

**By fund sponsor (attribution), te4 − flatten**, pp/yr (NW t). Sponsors are from `cef_facts.csv`. [V, `tables.py` P1]

| sponsor (names) | 2010-14 | 2015-19 | 2020-22 | FIT <2023 | H13 2023+ |
|---|---|---|---|---|---|
| **PIMCO (PCN, PDI, PDO, PFN, PHK, PTY)** | +3.46 (2.09) | +6.54 (2.31) | +5.12 (2.09) | **+3.63 (3.64)** | +0.35 (0.28) |
| BLACKROCK (BIT, HYT, MHD, MQY) | +0.05 (0.28) | −0.09 (−0.08) | −1.42 (−0.74) | −0.25 (−0.56) | +0.55 (0.62) |
| DOUBLELINE (DSL) | −0.16 (−1.52) | +0.79 (0.77) | +1.39 (1.28) | +0.41 (1.23) | −0.22 (−0.31) |
| NUVEEN (JFR) | +0.15 (0.72) | +0.30 (2.38) | +0.72 (1.87) | +0.24 (2.68) | −0.14 (−0.92) |
| ALLIANCEBERNSTEIN (AWF) | +0.78 (0.96) | −0.34 (−2.20) | +0.22 (0.74) | +0.16 (0.67) | +0.33 (2.35) |

- PIMCO carries 87% of the fit gap, in every era.
- Both legs contribute. On thin days the PIMCO long leg earns +2.25 and the short leg +1.25 [S: beta-detector pass].
- A reading [U]: this is relative-premium reversion inside one manager's funds. It is a mechanism, not beta, but its breadth is one family.

**Borrow.** It is charged through `bf.borrow_charge`, the harness's one definition: fee at t−1, 102% collateral, actual/360 on the shift(2) held book. It is charged nowhere else in this report. Paper charges none, so this is the real-money view. [V, `tables.py` J]

| vs | window | gross gap pp/yr | mean extra short weight | uniform fee that erases the gap |
|---|---|---:|---:|---:|
| flatten | 2010-14 | +4.28 | +0.126 | 32.9%/yr |
| flatten | 2015-19 | +7.19 | +0.435 | 16.0%/yr |
| flatten | 2020-22 | +6.03 | +0.258 | 22.5%/yr |
| flatten | FIT <2023 | +4.19 | +0.199 | 20.4%/yr |
| flatten | H13 2023+ | +0.87 | +0.118 | 7.1%/yr |
| hold | FIT <2023 | +2.48 | +0.014 | 174.5%/yr (te4 adds almost no short against hold) |
| hold | H13 2023+ | +0.90 | +0.026 | 32.8%/yr |

**Measured on the IBKR FEE_RATE panel.** The panel has no independent source for its levels before 2026-09 [S: `docs/REFERENCES.md`]. **Before 2021-09-13, borrow is UNMEASURED.**

| measured window | days | borrow, %/yr of NAV: hold / flatten / te4 | te4 − flatten, gross → net | te4 − hold, gross → net |
|---|---:|---|---|---|
| 2021-09-14 to 2022-12-30 | 328 | 13.25 / 7.49 / 12.42 | +7.72 → **+2.79** | +6.69 → +7.51 |
| 2023-01-03 to DIST_END | 921 | 6.99 / 4.81 / 8.01 | +0.87 → **−2.33** | +0.90 → −0.12 |

**Back-cast [U].** Each name's median measured fee, and then its p90 fee, is charged as a constant to every window. te4 − flatten net:
- fit period: **+2.21 at median fees, −2.67 at p90 fees**;
- H13: −0.37 and −4.32.

The fees behind it:
- PHK's median fee is 12.4%/yr (p90 45.0), PTY's 20.7 (p90 74.8) and PDI's 2.9 (p90 13.0).
- On the 2023 thin days te4's shorts paid 27.9%/yr, weighted by size, against a 6.7% median fee for the same names over 2023+. The signal shorts rich funds when they are expensive to borrow [S: beta-detector pass].

The extra short weight over flatten, fit period, by name: PDI +0.047, PTY +0.042, HYT +0.027, PHK +0.027, DSL +0.025, JFR +0.013, AWF +0.010, PCN +0.006.

## 6. The attack and its disposition

**Order.** `third_rule.py`'s docstring records each step.
- Attacks A to F were added after a first (smoke) run had printed the scoreboard, and before any of them ran.
- The direction control was declared before that run (seed 20261103, 500 draws).
- Attacks G to M were declared after the review and the beta-detector pass, before they ran here.
- The Dimson lag's derivation rule was declared in the finishing pass, before it ran.

### Summary

| # | attack | result (fit period unless stated) | disposition |
|---|---|---|---|
| A | where the thin-day P&L sits | eligible names 3.75 of 3.94; residues 0.19 | not a residue artefact |
| B | stale prices | held eligible name-days with zero return: 4.22% thin, 4.70% active; no zero-volume day | not stale prices |
| C | distributions and beta | price leg +4.22, distribution leg −0.28; beta to the EW universe −0.009 | not carry, not market beta |
| D | stretches as the unit | 24 stretches, run t 3.78, 20 positive | survives |
| E | best 10 days | 26.50 of 75.37pp; t 3.70 without them | survives |
| F | deflated bar, unmatched | t 4.51 clears 2.811 to 2.825; `read_result` PRESENT [+1.13, +7.26] | **superseded by H2**: not turnover-matched |
| H2 | matched turnover | +2.13 (t 2.34); INCONCLUSIVE [−0.87, +5.14] | **fails the bar** |
| G | sponsor | PIMCO +3.63 (t 3.64); the other seven +0.56 | **one family** |
| G2 | te4's own top two | PHK+PDI out: +1.08 (t 1.43) by attribution; +2.23 (t 3.55) rebuilt, from 2020-22 only | **two names, by attribution**; the methods disagree |
| H | independent episodes | 9, all positive, t 3.68 against 3.86; sign p 0.0020 against 0.00242 | **at the bar, not over it** |
| I | without the three largest stretches | +2.65 (t 3.27) | survives |
| J | recent-books placebo | thin P&L +3.94 at L 0, +1.80 at L 5, +0.46 at L 63; static tilt −1.63 | the current signal, decaying fast |
| K | extra execution delay | +3.06 (t 3.62) one session later, +2.38 (t 2.85) two | not a t+2 microstructure effect |
| L | factor regression, Dimson lag derived | alpha +6.26 (t 4.41); every \|β\| ≤ 0.06 | not factor beta |
| M | forward power | P(pass) 0.47 at 5 episodes (7 to 18 years) | **inadequate power** |
| — | direction control (H12) | p < 0.002 in every fit era; **p 0.242 on H13** | the direction matters in the fit period; not shown on H13 |
| — | H13 holdout | +0.87 (t 0.72), one episode | **not shown** |
| — | borrow | net −2.33 at measured 2023+ fees | **negative on real money where measured** |
| — | degenerate sessions | gaps unchanged under the sleeve's hold on 2020-03-18 and 2025-04-07 | no effect |

**Disposition: real gross P&L whose sign follows the signal, carried by PIMCO funds, not shown to be alpha:**
- under the repo's H2 rule it is INCONCLUSIVE;
- by attribution it is two names;
- as independent episodes it sits at the bar;
- on the holdout it is not shown;
- on real money borrow takes it;
- a forward test would take 7 to 18 years.

### A to C. Where te4's thin-day P&L comes from [V, `tables.py` K]

| window | te4 thin ann % | eligible names | band residues | residue gross | price leg | distribution leg | beta to EW universe | alpha part (NW t) |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2010-14 | 4.12 | 3.98 | 0.14 | 0.017 | 4.43 | −0.31 | −0.012 | 4.23 (3.00) |
| 2015-19 | 6.70 | 6.43 | 0.27 | 0.126 | 7.05 | −0.35 | −0.070 | 6.85 (2.52) |
| 2020-22 | 5.60 | 5.12 | 0.49 | 0.195 | 6.19 | −0.59 | −0.093 | 6.04 (2.74) |
| FIT <2023 | 3.94 | 3.75 | 0.19 | 0.056 | 4.22 | −0.28 | −0.009 | 4.00 (4.33) |
| H13 2023+ | 0.83 | 0.94 | −0.12 | 0.251 | 0.97 | −0.14 | −0.355 | 0.87 (0.88) |

**By eligible count at the decision.** Each cell is ann % of the window; then per thin earning day × 252; then NW t; [days].

| window | n = 4 | n = 5 |
|---|---|---|
| 2010-14 | +0.97; +7.07; t 1.03 [173] | +3.15; +25.55; t 3.34 [155] |
| 2015-19 | +1.60; +9.97; t 1.67 [202] | +5.10; +9.11; t 1.94 [704] |
| 2020-22 | +1.23; +23.88; t 1.93 [39] | +4.37; +11.12; t 2.05 [297] |
| FIT <2023 | +0.92; +10.07; t 2.39 [414] | +3.02; +11.83; t 3.55 [1156] |
| H13 2023+ | none | +0.83; +5.52; t 0.69 [138] |

**Stale-price signature.** The share of held name-days with a total return of exactly 0, over the fit period:
- thin, eligible: 4.22%;
- thin, residue: 6.42%;
- active, eligible: 4.70%;
- active, residue: 6.37%.

No held name-day had zero volume.

**The largest single name-days** are shorts that gained on sharp price drops while NAV was flat. For example, PHK on 2019-04-02 (price −12.28%, NAV 0.00%), decided on 2019-03-29 under shift(2) [S: beta-detector pass].

### D to F, H, I. The gap as a whole [V, `tables.py` K, P2]

| vs | FIT stretches | run t | positive | largest stretch (share) | best 10 days / total, pp | t without them | without the 3 largest stretches | paired t |
|---|---:|---:|---|---|---|---:|---|---:|
| flatten | 24 | 3.78 | 20/24 | 12.06pp (17%; 2019-03-27 to 2020-01-02) | 26.50 / 75.37 | 3.70 | +2.65 (t 3.27) | 4.51 |
| hold | 24 | 3.25 | 17/24 | 9.74pp (21%; 2016-03-24 to 2016-12-14) | 21.08 / 44.64 | **1.68** | +1.21 (t 1.56) | 3.03 |

**Independent episodes.** Stretches fewer than 63 sessions apart are merged. 63 is `build_panel`'s ADV window; it is asserted at run time, not swept.

| vs | FIT episodes | values, pp | t | positive | exact sign-flip p | N = 53: bar p / t(8) critical → t, sign | 2023+ episode |
|---|---:|---|---:|---|---:|---|---|
| flatten | 9 | +2.46, +10.96, +7.14, +21.38, +0.83, +12.06, +7.21, +1.68, +7.09 | 3.68 | 9/9 | 0.0020 | 0.00242 / 3.86 → **t fails, sign passes** | +3.02 |
| hold | 9 | +2.46, +8.45, +2.44, +13.72, +1.38, −0.09, +8.05, +0.90, +8.17 | 3.23 | 8/9 | 0.0039 | 0.00242 / 3.86 → **both fail** | +3.09 |

The readings at N = 52 and 54 are the same (`tables.py` P2).

### J. Recent-books placebo and a static tilt [V, `tables.py` P3]

Each placebo uses the same names on the same day, with the target rebuilt from the z-scores of L sessions earlier. Each cell is te4's thin-day ann %, then te4 − flatten in pp/yr (NW t), over the fit period:

| book | thin-day ann % | te4 − flatten (NW t) |
|---|---:|---|
| L 0 | +3.94 | +4.19 (4.51) |
| **L 5** | **+1.80** | **+2.01 (2.30)** |
| L 21 | +1.58 | +1.80 (2.00) |
| L 63 | +0.46 | +0.70 (0.79) |
| L 126 | +0.74 | +1.00 (1.25) |
| L 252 | +1.57 | +1.71 (2.02) |
| static fit-mean tilt (in-sample, which favours the placebo) | −1.63 | −1.39 (−1.36) |

- **The P&L is the current signal, and half of it is gone within five sessions.**
- This differs from PR #33's finding for hold, whose thin-day P&L any recent book earned.
- The L 252 residue may be the December-January seasonality that W4 found [U].

### K. Extra execution delay [V, `tables.py` P4]

Gaps in pp/yr (NW t), fit period:

| delay | te4 − flatten | te4 − hold |
|---|---|---|
| shift(2) | +4.19 (4.51) | +2.48 (3.03) |
| shift(3) | +3.06 (3.62) | +1.47 (1.91) |
| shift(4) | +2.38 (2.85) | +0.73 (0.95) |
| shift(6) | +1.86 (2.33) | +0.26 (0.31) |

### L. Factor regression, with the Dimson lag derived [V, `tables.py` P5]

**The lag.** The team lead asked on 2026-11-02 for the Dimson lag to be re-derived properly before its next reading. The second run had copied the beta-detector's lags 0..2.

**The rule, declared before it ran:**
- Dimson's summed betas exist because a thinly traded close answers a factor move late. So the lag count is measured on the instruments, never on the gap under test.
- The universe's equal-weight return is regressed on the four factors at lags 0 to 10: 2011-03-04 to 2022-12-30, n 2,968, HAC 8, R² 0.581.
- Each lag's four coefficients are tested jointly (HAC Wald).
- K is the last lag of the unbroken run of significant lags (p < 0.05) starting from lag 1.

**The result.** The Wald p by lag:

| lag | p |
|---|---|
| L1 | 0.0000 |
| L2 | 0.0179 |
| L3 | 0.1837 |
| L4 | 0.1557 |
| L5 | 0.4093 |
| L6 | 0.1532 |
| L7 | 0.0451 |
| L8 | 0.1757 |
| L9 | 0.4871 |
| L10 | 0.0078 |

**K = 2.** Lags 7 and 10 are significant in isolation, after a run of insignificant lags; the rule stops at the first gap. K = 2 equals the second run's lag, so no figure moved.

**The factors** come from the repo's ETF panel (to 2026-10-09): credit HYG − IEF, rates IEF, loans BKLN − IEF, equity SPY. The beta-detector's fifth factor, MUB, came from a scratch yfinance pull with no fetcher, so it is not used. Standard errors are HAC with the Newey-West 1994 lag.

| vs | sample | n | alpha pp/yr (t) | R² | credit | rates | loans | equity |
|---|---|---:|---|---:|---|---|---|---|
| flatten | **FIT, lags 0..2** | 2976 | **+6.26 (4.41)** | 0.004 | +0.017 (+0.6) | −0.016 (−0.5) | −0.009 (−0.3) | −0.006 (−0.4) |
| flatten | FIT, lags 0..2, thin days | 1931 | +9.06 (4.21) | 0.008 | +0.006 (+0.1) | −0.057 (−0.7) | −0.017 (−0.2) | −0.002 (−0.1) |
| flatten | FIT from 2007, 3 factors (no loans), lags 0..2 | 3958 | +4.85 (4.44) | 0.002 | +0.003 (+0.3) | −0.016 (−0.7) | − | +0.001 (+0.1) |
| flatten | H13, lags 0..2 | 921 | +1.12 (0.91) | 0.026 | −0.104 (−1.1) | +0.017 (+0.2) | +0.065 (+0.7) | −0.003 (−0.2) |
| flatten | FIT, lag 0 [sensitivity] | 2978 | +6.17 (4.43) | 0.002 | +0.038 (+2.1) | +0.030 (+1.4) | −0.011 (−0.9) | −0.010 (−1.1) |
| flatten | FIT, lags 0..1 [sensitivity; the repo's W4 convention] | 2977 | +6.34 (4.51) | 0.003 | +0.029 (+1.1) | +0.008 (+0.3) | −0.003 (−0.2) | −0.018 (−1.4) |
| hold | FIT, lags 0..2 | 2976 | +3.74 (2.91) | 0.003 | +0.000 (+0.0) | −0.043 (−1.5) | −0.008 (−0.3) | −0.005 (−0.3) |
| hold | H13, lags 0..2 | 921 | +0.50 (0.52) | 0.073 | +0.065 (+1.4) | +0.064 (+0.6) | +0.046 (+0.5) | −0.017 (−1.3) |

- The fit alpha t is 4.41 to 4.51 at every lag, so the conclusion does not depend on the lag.
- Every fit-period beta is 0.06 or less in absolute value. On H13 the credit beta is −0.104 (t −1.1).
- The daily alpha here is larger than the paired gap (+4.19), probably because the factor sample starts in 2011-03, after the flat early years [U].

### M. Power of a forward test [V, `tables.py` P6]

**The inputs:**
- The per-episode effect (mean/sd of the 9 fit episodes) is 1.23.
- The holdout's per-day edge is 0.49 of the fit period's: +5.52 against +11.37%/yr per traded thin earning day.
- Episodes per year: 0.71 over the fit period (from 2010-05-05), and 0.27 since 2023.

P(pass) from `inference.p_clear_bar`, at the fit / shrunk effect. It is a normal approximation, generous at small n.

| N | 2 episodes | 3 | 5 | 9 | 13 |
|---|---|---|---|---|---|
| 53 | 0.14 / 0.02 | 0.24 / 0.04 | 0.47 / 0.07 | 0.81 / 0.15 | 0.95 / 0.25 |
| 54 | 0.14 / 0.02 | 0.24 / 0.04 | 0.47 / 0.07 | 0.81 / 0.15 | 0.95 / 0.25 |

Five episodes would take 7.0 years at the fit rate, and 18.4 at the rate since 2023. At the day level, a coin-flip pass needs about 686 thin earning days. That assumes the days are IID, and is overstated if they are autocorrelated.

### Direction control (H12) [V, `tables.py` L]

On every session te4 trades, the reduced-set target's weights are reassigned among that session's own eligible names, in a random order drawn once per thin stretch. The names, the gross and the weight distribution are unchanged. Only the direction relative to the signal is random.

| window | te4 | null mean | null sd | null 95th pct | P(null ≥ te4), 500 draws |
|---|---:|---:|---:|---:|---|
| 2010-14 | +4.12 | −0.19 | 0.88 | +1.38 | < 0.002 (0 of 500) |
| 2015-19 | +6.70 | −0.16 | 2.34 | +3.56 | < 0.002 |
| 2020-22 | +5.60 | +0.11 | 1.31 | +2.27 | < 0.002 |
| FIT <2023 | +3.94 | −0.08 | 0.71 | +1.13 | < 0.002 |
| H13 2023+ | +0.83 | +0.05 | 0.92 | +1.48 | **0.242** |

### The two degenerate sessions [V, `tables.py` M]

On 2020-03-18 and 2025-04-07 the harness cuts to the band edge, while the live sleeve holds (PR #33 §5.H). Replayed with the sleeve's behaviour:
- every rule loses about 0.6pp/yr on H13 (te4 11.50 → 10.91);
- te4 minus flatten and te4 minus hold do not change in any window.

### Not re-run here [S: beta-detector pass]

- Per unit of gross, thin sessions earned 10.06%/yr against 6.77 on active ones over the fit period.
- In 2010-14 the thin-day Sharpe was 2.90, against 0.74 for the active book.

This is unexplained. It sits awkwardly with W4's finding that the deployed 13-name signal is not significant in any single era [S: `docs/BRIEF.md`]. The hindsight universe (the answer, §2) is the most plausible boring explanation [U].

## 7. Forward relevance and the expected effect on the current book

**Eligible count by year since 2023** [V, `tables.py` N]

| year | sessions | n = 4 | n = 5 | n = 6 | n = 7 | n ≥ 8 | min |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 250 | 0 | 138 | 105 | 7 | 0 | 5 |
| 2024 | 252 | 0 | 0 | 114 | 119 | 19 | 6 |
| 2025 | 250 | 0 | 0 | 0 | 60 | 190 | 7 |
| 2026 (to 2026-10-14) | 197 | 0 | 0 | 1 | 0 | 196 | 6 |

**How close the book runs to thin:**
- The last thin session was **2023-08-30**. Of the 783 sessions since, 192 had exactly 6 eligible names (the last on 2026-02-12) and 186 had exactly 7 (the last on 2025-08-15).
- On the 406 sessions since 2023 with 6 or 7 eligible names, the least liquid eligible name's ADV sat at 1.00 times the floor at the minimum, 1.03 times at p10 and 1.13 times at the median.
- The marginal name was most often HYT (129 sessions), PCN (103), PHK (61), MQY (50) and JFR (47).
- On 2026-10-14, AWF was just under the floor [S: PR #33 §5.I].

**What the rule would have changed since 2023-08-30: nothing.** With 6 or more eligible names, the three rules build the same target.

**What the rules earned on the actual 2023+ thin sessions** (2023-02-13 to 2023-08-30, 138 earning days):
- te4 earned **+3.02pp**, at a mean gross of 1.269;
- hold earned −0.07pp, at a mean gross of 0.863;
- flatten earned 0.

**A hypothetical [U].** On each 6- or 7-name session since 2023, drop the least liquid eligible names until 5 (or 4) remain. This assumes the names nearest the floor fall out first. 2025-04-07 is skipped, because its full target is 0/0.

| names left | sessions | flatten would close a held book of gross (median) | te4 target's cosine to the full target, median (p10) | te4 target gross (median) | te4 max \|w\|, median (p90) |
|---|---:|---:|---|---:|---|
| 5 | 405 | 1.309 | 0.82 (0.49) | 1.204 | 0.457 (0.749) |
| 4 | 405 | 1.309 | 0.60 (0.31) | 1.190 | 0.493 (1.116) |

On a one-name dip, flatten exits the whole book. te4 keeps a book pointing mostly the same way, but more concentrated.

**The expected annual effect on the current book [U].**
- **The arithmetic:** the gap per unit share of sessions that te4 trades and flatten does not, times a forward share.
- **The current book** is built as trial 53 is activated: m × `band_gross_capped(T, band, 1.8 / m)`, with m = 1.13 read from `release-20261102-1`'s spec. The reading of the spec is [V]; whether prod runs that tag is [S].
- **Extra borrow** per unit share at 2023+'s measured fees is +21.36 on the unit book and +21.96 at m.

| base | gap, unit (NW t) | share traded | per unit share, unit (deferred) | forward share | gross unit (deferred) | gross at m | extra turnover @15bp, unit / m | extra borrow at 2023+ fees, unit / m | net unit / m |
|---|---|---:|---|---|---|---:|---|---|---|
| H13 2023+ (the out-of-sample analogue) | +0.87 (0.72) | 15.0% | +5.81 (+4.08) | 0 (since 2023-08-30) | 0.00 | 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |
| H13 2023+ (the out-of-sample analogue) | +0.87 (0.72) | 15.0% | +5.81 (+4.08) | **2023's share, 15.0%** | +0.87 (+0.61) | **+0.84** | 0.39 / 0.44 | 3.20 / 3.29 | −2.72 / **−2.89** |
| FIT <2023 | +4.19 (4.51) | 34.7% | +12.10 (+11.23) | 0 | 0.00 | 0.00 | 0.00 / 0.00 | 0.00 / 0.00 | 0.00 / 0.00 |
| FIT <2023 | +4.19 (4.51) | 34.7% | +12.10 (+11.23) | 15.0% | +1.81 (+1.68) | +1.97 | 0.70 / 0.79 | 3.20 / 3.29 | −2.09 / −2.11 |
| 2015-22 (thin = 4-5 names) | +6.76 (3.54) | 61.7% | +10.95 (+10.17) | 15.0% | +1.64 (+1.52) | +1.76 | 0.79 / 0.89 | 3.20 / 3.29 | −2.35 / −2.43 |

**Reading [U].**
- **Today the effect is zero**, and it stays zero until a session is thin.
- **On paper** (gross, no borrow, no cost): if thin sessions recur at 2023's share, about +0.8 to +2.0pp/yr at m. The low end is the only out-of-sample analogue.
- **On real money:** negative in every row, because the extra shorts are in the funds most expensive to borrow.
- **The forward share is unknown.** It was 0 for the last 783 sessions, and one ADV dip of the marginal name would change that.
- **Composition with the vol scalar and trial 53:**
  - The vol scalar sits inside the target and is re-estimated on the book's own trailing 63 sessions, so it already shrinks a concentrated reduced-set book.
  - m then scales whatever book the rule leaves, with the ceiling at 1.8/m.
  - Trial 53's m was derived on the hold book's daily sd (PR #33 §6), and the owning session is re-measuring it on the flatten book.
  - Under te4 the thin-session book differs from both. m would need re-measuring on te4's book if te4 were ever adopted (open question 2).

## 8. Why no pre-registration is drafted

The task allows a draft only if the third rule survives the attack as plausible alpha with adequate power. It does not:
- **It is not plausible alpha by the repo's own rules.**
  - At matched turnover (H2) it is INCONCLUSIVE: t 2.34, under 2.818.
  - By attribution it is PHK and PDI (t 1.43 without them), and 87% one sponsor.
  - As independent episodes it sits at the bar (t 3.68 against 3.86).
  - On the holdout it is not shown (t 0.72; direction-control p 0.242).
- **It has no adequate power.** A forward test passes with P 0.47 after five new episodes at the fit effect (0.07 at the shrunk effect). That would take 7 to 18 years, and no thin session has occurred since 2023-08-30.
- **The holdout is already seen.** This report prints te4's 2023+ rows, so H13 is no longer unseen evidence for this rule. The only unseen evidence would be forward thin sessions.
- **For real money**, measured borrow exceeds the holdout gap.

**What a test would need, if the team lead wants one later** [U]:
- CEF trial N (assigned at approval), through `/prereg` and `/spec-change`.
- **The unit of inference:** stretches or episodes, with the merge rule fixed in advance (open question 7).
- **The bar** at the counter's N.
- **Turnover matched within 5% (H2)**, with the device fixed in advance (open question 5).
- **Leave-outs declared as gates:** PHK, PHK+PDI and the PIMCO family, with the leave-out method fixed in advance (open question 6).
- **Borrow** from the IBKR panel, with the edge required to survive the 2023+ fee regime.
- **Deferred flips**, as the live runner uses.
- **The min-weight guard decided** (l.928).
- **The live-path pieces decided:**
  - the floor test at l.841;
  - `src/deploy/registry.py::cef_below_min_names`, which accepts only "flatten" and "hold";
  - the runner's `gate.max_missing_nav_holds` and its `SHORT_OF_MIN_NAMES` tagging in `docs/RUNNER.md`.
- **A statement of composition:** with trial 53's `sizing_multiplier`, with the vol scalar, and with the owning session's re-measure of trial 53 on the flatten book.

## 9. Defects found by the passes, and what was done

| # | from | finding | verdict | done |
|---|---|---|---|---|
| 1 | review | the headline (t 4.51, PRESENT) is not turnover-matched; H2 allows matched comparisons only | confirmed [V] | `matched` prints the gap, t, bar and `read_result` at matched turnover; the headline is now INCONCLUSIVE (+2.13, t 2.34) |
| 2 | review | the gross ceiling under "trade_eligible" was untested (mutants N3 and N12 survived) | confirmed [V] | test 7 added; both mutants now fail it, re-checked in the finishing pass [V] |
| 3 | review | the forward estimate was about twice its only out-of-sample analogue, and ignored borrow | confirmed [V] | the 2023+ analogue is a base; the m book is built as trial 53 is activated; extra borrow is charged |
| 4 | review | the borrow block re-implemented the harness's borrow charge (understated by about 2-3%, no sign change) | confirmed [V] | borrow goes through `bf.borrow_charge`; the 2023+ net moved from −2.27 to −2.33 |
| 5 | review | `read_result`'s `meaningful` was the estimate, so ABSENT was unreachable | confirmed | it is now the cost hurdle (extra turnover at 15bp) |
| 6 | review | tracked docstrings cite this REPORT.md, which was not committed | confirmed | this file |
| 7 | beta-detector | the two-name leave-out used hold's top two (PHK, PTY); te4's are PHK and PDI | confirmed [V] | PHK+PDI and PHK+PDI+PTY added, by attribution and rebuilt |
| 8 | beta-detector | one fund family carries the gap | confirmed [V] | sponsor split added (P1) |
| 9 | beta-detector | the 24 runs are not independent; at 9 episodes the gap is at the bar | confirmed [V] | episodes added (P2); the reading is now "at the bar" |
| 10 | beta-detector | the recent-books placebo was missing | confirmed | added (P3); it supports the current-signal reading |
| 11 | beta-detector | "it held up under every attack" was overstated | confirmed | withdrawn; the answer now lists what it does not survive |
| 12 | beta-detector | factor beta untested on committed code | confirmed | regression added on the repo ETF panel, without the scratch MUB series |
| 13 | finishing pass | the regression's Dimson lag (0..2) was copied, not derived | confirmed | the lag is derived on the instruments (K = 2); lags 0, 1 and 2 printed; no figure moved |
| 14 | beta-detector | the brief's CEF counter (48) is stale | confirmed [V, `git show`] | `main` and this branch read 52; `release-20261102-1` reads 53 |

No finding was refuted.

## Not modelled (all rules)

- **`min_abs_weight`.** The live sleeve's min-weight block acts on 127 of te4's 1,708 reduced sessions. The largest weight difference is 0.005 (§2).
- **Whole shares.**
- **Run-time holds**: the stale-NAV gate and the missing-NAV hold.
- **Paper's `late_market` fills.**
- **Borrow**, except in §5 and §7.
- **Distributions.** Returns are total returns, but paper pays no distributions.
- **The hindsight universe** [S: PR #33, beta-detector pass].
  - 77% of fit earning days (3,484 of 4,531) follow a thin decision, in years when the 2026 universe is projected back.
  - The reduced set is liquid by its own day's test (ADV ≥ $3m through t−1), but the choice of the 13 names is not point-in-time.
- **Survivorship**, which these files cannot measure.

## Reproduce (from the worktree root)

```
python3 results/backtests/thin-third-rule-2026-11-03/noop_hash.py               # default-path hashes (compare noop_before.txt / noop_after.txt)
python3 results/backtests/thin-third-rule-2026-11-03/sleeve_reduced_check.py    # the live sleeve on all 3,622 thin sessions -> sleeve_reduced.csv (about 5 min)
python3 results/backtests/thin-third-rule-2026-11-03/third_rule.py              # every section -> run.log (gitignored), results.json (about 6 min)
python3 results/backtests/thin-third-rule-2026-11-03/tables.py                  # every table above, from results.json
python3 -m pytest scripts/cef/tests/test_band_trade_eligible.py scripts/cef/tests/test_band_below_min_names.py
```

Notes on `third_rule.py`:
- It imports PR #33's `thin_days.py` and `attack.py` from `results/backtests/thin-days-2026-11-03/`.
- It needs that folder's `sleeve_thin.csv`.
- It reads `release-20261102-1`'s frozen spec with `git show` (read-only), and raises if the clone lacks the tag.

**Committed:**
- 5b4b2d3: the harness option, tests 1 to 6, `third_rule.py`, `tables.py`, `sleeve_reduced_check.py` and the no-op files.
- f5a5b9e: the review and beta-detector fixes and attacks, and test 7.
- 0a8795a: the derived Dimson lag and the re-run `results.json`.
- This report is in none of these commits (see the header).

## Open questions for the team lead

1. **The live thin-session rule.** The options are:
   - (a) keep flatten, the standing ruling of 2026-11-02;
   - (b) pre-register te4 as CEF trial N (assigned at approval), with §8's requirements, knowing a forward test is underpowered for years;
   - (c) neither, and record this screen.

   Nothing is chosen here. What the evidence shows:
   - On this panel te4 has the highest gross return in every window.
   - Against flatten, its edge is not shown to be alpha.
   - Against hold, its edge is not robust.
   - On real money, measured borrow exceeds its holdout gap.
2. **Trial 53 and the thin rule.** Trial 53's m was derived on the hold book (PR #33 §6), and the owning session is re-measuring it on the flatten book. If the thin rule ever changes, m needs re-measuring on that rule's book.
3. **The min-weight guard** (`cef_discount.py` l.928, `len(keep) >= min_names`). Under any reduced-set rule it would never re-neutralise. It matters only if option (1b) is chosen.
4. **The ADV margin.** Since 2023, on 6- and 7-name sessions, the least liquid eligible name sat at a median 1.13 times the floor (p10 1.03). Every thin-session rule is one ADV dip from binding.
5. **The H2 device for a reduced-set rule.** The declared device re-bands te4 on every session. A device that widens the band only on thin sessions might be the fairer control.
   - It was not run here, because choosing a device after seeing the declared one's answer would be choosing on the result.
   - It would not change §8: the power and holdout problems stand under either device.
6. **The leave-out method for any gate.** Attribution without PHK and PDI gives t 1.43. The universe rebuilt without them gives t 3.55, but only from 2020-22.
7. **The unit of inference.** The candidates:
   - daily NW t: 4.51, unmatched;
   - the 24 raw runs: t 3.78;
   - the 9 episodes merged at the 63-session ADV window: t 3.68, a t(8) miss and a sign-test pass by a hair.
8. **Borrow history.** There is no point-in-time borrow for PHK, PDI or PTY before 2021-09-13. A securities-lending history would settle the real-money question for this rule, and for any rule that adds PIMCO shorts.
9. **The PIMCO concentration.** 87% of the fit gap is one sponsor's funds. That weighs against the desk's breadth problem: effective breadth is about 1 to 2 [S: `docs/BRIEF.md`].
10. **The counter.** CEF reads 52 on `main` and 53 at `release-20261102-1` [V, `git show`]. The owning session reconciles it.
