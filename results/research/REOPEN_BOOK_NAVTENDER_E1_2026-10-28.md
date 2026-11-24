# NAV tenders and E1, judged by what they add to the CEF book — fit period only, 2026-10-28

**Zero trials. No counter, spec or `docs/RESEARCH_STATE.md` edited. No holdout opened. It decides nothing.**
Branch `research-reopen-book`, cut from `desk-research-method` at db88b14. Revised the same day after an independent review (§6).
**Reproducer:** `python3 -m scripts.research.reopen_book.reopen_book`, i.e. `scripts/research/reopen_book/reopen_book.py`
(about 30 s; writes `results/research/reopen_book/reopen_book_2026-10-28.json`, run at b830366 on a clean tree). Tests:
`python3 -m pytest scripts/research/tests -q`.
It needs the worktrees `trial-events-navtender` (ac2c7ca) and `trial-events-e1` (6d8bdbf) with their
CRSP caches, and `data/` linked as in the other worktrees. Every figure below marked **[V]** comes
from that command's JSON. **[S]** marks a figure read from a trial's committed note or fit JSON.

## 0. The answer

The team lead's rule (`docs/SYSTEM.md` §5, 2026-10-27, "Admission by marginal contribution") has two
limbs. A sleeve that fails the standalone deflated Sharpe may join the **paper** book, labelled, if:
1. SR_sleeve > ρ·SR_book across ρ's range; and
2. the combined book's net is positive at 5, 15 and 30bp.

Both limbs are measured on the fit-period dates the sleeve and the book share: 2013-06-25 to
2022-12-30, T = 2,398 sessions. The book holds nothing before 2013-06-25. There are two views:
- **Total:** book and sleeve on total returns (H15).
- **Paper:** book **and** sleeve on price returns, because Alpaca paper pays no distributions
  (CLAUDE.md landmine 1). The sleeve's price-return P&L is built on the same positions (§1).

| [V] | NAV tenders, total | NAV tenders, **paper** | E1, total | E1, **paper** |
|---|---|---|---|---|
| days active of 2,398 (median spell) | 1,680 (60 sessions) | same | 1,492 (120 sessions) | same |
| distribution leg in the sleeve's return | **+1.48 of +1.80%/yr** | removed | +0.08 of +0.93%/yr | removed |
| **1.** gross Sharpe; net 5 / 15 / 30bp | 0.382; 0.314 / 0.180 / −0.022 | **0.055**; 0.001 / −0.108 / −0.271 | 0.273; 0.238 / 0.168 / 0.063 | 0.248; 0.213 / 0.143 / 0.038 |
| DSR at N = 6: desk bar · paper bar | 0.245 · 0.453 | 0.045 · 0.134 | 0.146 · 0.323 | 0.128 · 0.295 |
| sleeve mean, Newey–West t (auto lag) | 1.43 | 0.19 | 1.14 | 1.04 |
| book gross Sharpe in that view | 0.955 | 0.959 | 0.955 | 0.959 |
| **2.** ρ, daily point; range (§2.2) | +0.086; [−0.174, +0.195] | +0.062; [−0.129, +0.251] | +0.021; [−0.278, +0.086] | +0.020; [−0.305, +0.066] |
| ρ without 2020-02-15 to 04-30 (52 sessions) | +0.011 | +0.000 | +0.022 | +0.021 |
| break-even ρ = SR_sleeve / SR_book | 0.399 | 0.058 | 0.286 | 0.258 |
| **3.** marginal gain, gross: point / high end | +0.299 / +0.196 | **−0.004 / −0.185** | +0.253 / +0.191 | +0.228 / +0.185 |
| marginal gain at 30bp: point / high end | −0.050 / −0.087 | −0.294 / −0.361 | +0.056 / +0.035 | +0.031 / +0.015 |
| **4.** combined gross Sharpe (book alone) | 0.959 (0.955) | **0.738** (0.959) | 0.965 (0.955) | 0.960 (0.959) |
| combined net 5 / 15 / 30bp | 0.840 / 0.603 / 0.248 | 0.630 / 0.413 / 0.088 | 0.858 / 0.644 / 0.323 | 0.855 / 0.646 / 0.332 |
| book alone, net 5 / 15 / 30bp | 0.852 / 0.645 / 0.334 | 0.859 / 0.658 / 0.356 | 0.852 / 0.645 / 0.334 | 0.859 / 0.658 / 0.356 |
| with the 1.80× ceiling (approximate): gross; net 30bp, no rescaling cost to the bound | 0.933; 0.221 to 0.020 | 0.772; 0.101 to −0.088 | 0.960; 0.331 to 0.174 | 0.932; 0.318 to 0.165 |
| combined held gross: mean · max · days above 1.80× | 1.83 · 3.50 · 48.2% | same | 1.98 · 3.60 · 50.1% | same |
| **5.** reading | **Meets the rule across ρ's range** at gross, 5bp and 15bp; fails limb 1 at 30bp | **Does not meet**: the gain is ≤ 0 at the point estimate, at gross and at every cost | **Meets the rule across ρ's range**, at every cost | **Meets the rule across ρ's range**, at every cost |

**NAV tenders' eligibility depends on the return convention.**
- On total returns it meets the rule.
- On the paper account's convention, 1.48 of its 1.80%/yr is distributions, which paper does not pay.
  What is left is a Sharpe of 0.055, and adding the sleeve lowers the book's.
- E1 does not depend on the convention: its distribution leg is 0.08%/yr, and it meets the rule in
  both views.

For E1 in both views, and for NAV tenders on total returns, the rule's arithmetic is not what binds:
- their break-even ρ sits above every interval measured.
- At the equal-risk weight (§2.4):
  - the combined book needs more than the frozen 1.80× gross ceiling on about half its days;
  - each sleeve earns less per unit of gross than the book (total view: NAV tenders 2.88%/yr, E1
    1.20%/yr, the book 5.15%/yr);
  - in the total view E1 lowers the book's net Sharpe at 15bp (0.6439 against 0.6446) and at 30bp;
    in the paper view, at every cost.
- With the ceiling applied, the total view's gross Sharpe is 0.933 with NAV tenders and 0.960 with
  E1, against the book's 0.955.

## 1. Team lead, 2026-10-28

Ruled on the first version of this note (b43bf35), before the paper-view finding in §6:

> "Kept the paper-admission rule as written, after seeing that, under the 1.80× cap, NAV tenders
> lowers the book's Sharpe and E1 leaves it flat."

- The ruling is recorded in `docs/SYSTEM.md` §5, in "Team lead, 2026-10-27: the research method",
  dated 2026-10-28.
- It reached this note through the coordinating agent.
- **The paper view (§0, §6) was found afterwards, by an independent review.**

**Team lead, 2026-10-28, later, on the paper view.** Paper's own P&L of record decides paper
admission. **NAV tenders does not qualify** for the paper book; it remains a real-capital
candidate on total returns. **E1 qualifies.** It goes next to `quant-trader`'s rollout:
- a broker check (whether Alpaca paper processes a merger conversion is [U]);
- then shadow;
- then a paper sleeve.

Recorded in `docs/SYSTEM.md` §5.

## 2. The series

| series | how it was built | check |
|---|---|---|
| NAV tenders: tradable sleeve, daily, 2010-03-24 to 2022-12-30 | `scripts/research/reopen_book/extract_trial_series.py navtender`. It runs the branch's own committed `scripts/events/nav_tender_trial.py` (`stage0(write=False)`, then `run_pnl` with the fit's k and the 1.80 cap at entry) from that worktree | reproduces `results/events/nav_tender/fit_2026-10-19.json` exactly: gross 0.450, nets 0.381 / 0.244 / 0.037, vol, turnover, T 3,217, k [S], max abs difference 0.0 [V] |
| E1: tradable muni sleeve, daily, 2009-06-23 to 2022-12-30 | the same script, `e1`. It runs `scripts/events/e1_merger_pair.py`'s `fit()` steps up to `sleeve(...)`; control 2's pick is skipped because the sleeve never reads it | reproduces `results/events/e1/e1_fit_verdict.json` exactly: gross 0.281, nets 0.244 / 0.170 / 0.059, k, T 3,406, 98 deals [S], max abs difference 0.0 [V] |
| each sleeve on **price returns** (the paper view), same positions | **A:** the trial's own builder re-run on CRSP `retx` and `dlretx` in place of `ret` and `dlret` (`build_matrices` with the tradable weights; `returns_matrix`). **B:** an overlay, Σ H.shift(2)·(ret − retx) on the tradable H, with a tendered fund's column scaled by (1 − π) from its pricing session; ETF hedges on the permnos from `etf_permnos_resolved` | **A and B agree to 3.5e-18 (NAV tenders) and 1.3e-18 (E1) a day** [V]. They share the H and the CRSP rows, so the agreement checks the arithmetic, not the data. B carries no delisting distribution; none bites in the held cells |
| CEF book, daily, live policy | `build_targets` on the `data/cef/` price and NAV panels **cut at 2022-12-30 before any computation** (`source=`), then `band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)` and `evaluate()` on `total_returns` (total view) or price returns (paper view). The spec is `cef_discount.v7.20260928`, "band 4.8% + gmax 1.80x". Full panels end 2026-10-15 (prices) and 2026-10-14 (NAV) | **second method:** both trials' own R-BOOK correlations, built on the full panel, are reproduced to six decimals: 0.086320 (n 2,398) and 0.016656 (n 3,406) [V], against the trials' [S] |

- **`total_returns` reads the full distribution, split and price panels** and reindexes them to the
  fit index.
- The script asserts that cutting those three inputs at 2022-12-30 too leaves the distribution yield
  and the split factor unchanged, cell for cell (`assert_return_inputs_cut`).
- The cut drops 1,831 distribution rows and one split row.
- So no 2023+ value reaches any figure.
- Neither trial stored a daily series. The re-derived ones stay in the gitignored
  `results/research/reopen_book/_cache_reopen/`.
- Nothing was written in either trial's worktree: `git status --ignored` and the mtimes were
  unchanged.
- The extractor makes the R2 client unimportable, refuses a CRSP cache miss, and installs
  `ops.netguard`.

## 3. How each item was computed (rules in the script's docstring before its first run)

The trials' own aggregates were already published, so these rules are not blind to the sleeves'
Sharpes. They are blind to this measurement.

- **Item 1.**
  - `band_frontier._stats` on the common window, each sleeve on its own cost convention:
    - NAV tenders charge notional on every leg, 6.34 turns/yr;
    - E1 charges event turnover, where a conversion is not a trade, 2.37 turns/yr.
  - `inference.desk_dsr(SR, T, skew, kurt, 6)`, asserted equal to `dsr(..., 1/T, bound="upper")`, with
    `bound="gumbel"` beside it. N = 6 is EVENTS' declared bar.
  - Own-span rows reproduce the trials: desk DSR 0.392 and 0.194 [V], as the trials got [S].
- **Item 2.** The range is the union of five intervals:
  - three daily stationary bootstraps (10,000 pair draws, seed 20261028). The mean blocks are the
    sleeve's median active spell (60 or 120 sessions; measured from holdings, never P&L), and 21 and
    63, the two trials' declared blocks;
  - Fisher intervals on weekly sums (n 497) and on 21-session sums (n 114). The 21-session sums are
    `PORTFOLIO_FRAMEWORK_2026-10-15.md` §2.4's input.
  - Both statistics are in `scripts/research/inference.py` (`stationary_bootstrap_corr`,
    `fisher_corr_ci`). The draw is pinned to `w4_artifacts.stationary_boot`'s, and the Fisher interval
    to scipy's.
- **Item 3.** `inference.marginal_gain` at the point estimate and both ends, on gross Sharpe and on each
  net level.
- **Item 4.**
  - **The weight rule:** equal risk budgets. `PORTFOLIO_FRAMEWORK` §2.3 sets b ∝ R̃⁻¹·1 with fewer than
    four sleeves, which for two sleeves is equal budgets. An event sleeve's budget is a ceiling (§2.2).
    So each enters at its own pre-registered sizing, and **combined = book + 1.0 × sleeve**. Nothing is
    optimised.
  - Costs and gross add, with no netting. Neither sleeve trades a book symbol [S, from each branch's
    code]: NAV tenders' Stage 0 drops in-universe funds, and E1's `e1_prereg_counts.partition`
    excludes spec names.
- **The ceiling row (approximate).**
  - The ceiling is f = min(1, 1.80 / G) on each decision row. P&L is scaled by the f decided two
    sessions earlier, and turnover by its own row's f.
  - The rescaling trade (f_t − f_{t−1})·w_{t−1} is bounded by Σ|Δf|·G(t−1): **at most 5.03 turns/yr
    for NAV tenders and 3.21 for E1** [V]. The capped nets are reported from no rescaling cost to that
    bound.
  - The band's feedback into the next day's trade is not rebuilt.

| total view [V] | NAV tenders | E1 |
|---|---|---|
| capped net 5 / 15 / 30bp, no rescaling cost | 0.815 / 0.577 / 0.221 | 0.855 / 0.646 / 0.331 |
| capped net 5 / 15 / 30bp, at the bound | 0.781 / 0.477 / 0.020 | 0.829 / 0.567 / 0.174 |
| plain `band()` book (no ceiling) + sleeve: gross; nets | 0.945; 0.829 / 0.596 / 0.248 | 0.956; 0.851 / 0.640 / 0.324 |
| E1 on the harness's turnover **measured on the sized H** (4.00/yr): sleeve nets; combined nets | — | 0.214 / 0.096 / −0.080; 0.847 / 0.611 / 0.257 |
| long-only optimum at the point ρ (`combined_sharpe`; a ceiling, not a weight) | 1.001 gross | 0.988 gross |

**Leverage**, as held gross Σ|w| against `max_gross_stress` 1.80 [V]:

| | NAV tenders | E1 |
|---|---|---|
| book alone: mean / p95 / max | 1.21 / 1.80 / 1.80 | same |
| sleeve alone: mean / p95 | 0.62 / 1.61 | 0.77 / 1.80 |
| combined: days above 1.80 | 48.2% | 50.1% |
| combined, counting only days the sleeve is active | 68.8% | 80.6% |
| combined rescaled to the book's own vol: days above 1.80 | 27.1% | 43.4% |
| annual return per unit of held gross, total view: book / sleeve | 5.15% / 2.88% | 5.15% / 1.20% |
| the same, paper view | 5.33% / 0.52% | 5.33% / 1.09% |

## 4. The caveats that matter

1. **The return convention decides NAV tenders** (§0). Its daily ρ also comes from the 2020 crash: it
   falls from 0.086 to 0.011 without 2020-02-15 to 04-30 [V].
2. **The sleeve's Sharpe is the noisy input, not ρ.**
   - The Newey–West t is 1.43 and 1.14 in the total view, and 0.19 and 1.04 in the paper view.
   - The daily bootstrap intervals are narrower than the summed ones. Read the summed rows as the
     range.
3. **Limb 2 is weak as written.**
   - The book alone nets 0.33–0.36 at 30bp, so almost any sleeve leaves the combined net positive.
   - Against the book's own net at the equal-risk weight:
     - in the total view NAV tenders lowers it at every cost, and E1 at 15bp and 30bp;
     - in the paper view both lower it at every cost.
4. **The gross ceiling binds before the vol budget does.** Both sleeves earn less per unit of gross
   than the book, so under a binding gross budget (framework §2.5) each unit they take displaces
   book gross that earns more. `max_gross_stress` was not re-derived on the combined book (§2.7).
5. **Overlap.**
   - The window drops 2009/10–2013, because the book was flat then. That is where NAV tenders'
     own-span 30bp net is positive (+0.037).
   - Holdings overlap in time (median spells of 60 and 120 sessions), which is why the blocks and the
     sums were used.
   - Whether the two sleeves share symbols with each other was not measured.
6. **Cost conventions.**
   - Each leg is costed on its own convention.
   - **E1's harness turnover, as committed by its trial, is mis-scaled.** `e1_merger_pair.sleeve`
     (branch `trial-events-e1`, line 1049) returns the turnover of the raw, uncapped H beside P&L on
     the sized and capped H. So `e1_fit_verdict.json`'s `harness_turn` 14.40/yr, and its note's "the
     harness counts 14.40/yr", overstate it.
   - Measured on the sized H it is 4.21/yr on E1's own span and 4.00/yr on this window [V]. That
     branch is not edited here.
   - Borrow and NAV tenders' election fee are left out, since paper charges no borrow. They matter for
     real capital, which keeps the standalone gate.
7. **Paper mechanics are unmeasured [U].**
   - The paper view removes only distributions.
   - Whether Alpaca paper processes a voluntary tender election or a merger conversion was not
     measured. The tender's own payoff (A − B) is +0.634% of NAV tenders' +1.084% per event [S].
8. **Eras (H5)** [V]: sleeve Sharpe, total / paper, each era clipped to the window.

| era | NAV tenders | E1 | book, total / paper |
|---|---|---|---|
| 2013-06-25 to 2014-12 (384 sessions) | 0.393 / 0.394 | −0.216 / −0.256 | 1.298 / 1.631 |
| 2015-19 | −0.020 / **−0.430** | 0.320 / 0.279 | 0.835 / 0.719 |
| 2020-22 | 0.749 / 0.625 | 0.450 / 0.449 | 1.020 / 1.084 |

## 5. What this does not do

- It spends no trial. EVENTS stays at 2, with its bar at N = 6.
- It opens no holdout. Every series ends 2022-12-30, asserted in the extractor and in
  `common_window`.
- Admission is the team lead's call, and the paper view (§0) is not yet ruled on.

## 6. Corrections, 2026-10-28 (independent review of b43bf35)

The first version's figures are kept here so that anyone relying on them can see what moved.

| first version (b43bf35) | corrected (b830366) | why |
|---|---|---|
| a paper row that put the book on price returns but kept the sleeve on total returns | the full paper view, both legs (§0) | Paper pays no distributions on either leg (landmine 1). NAV tenders' reading flips from "meets" to "does not meet" |
| E1 on the harness's turnover: 12.33/yr; combined net at 30bp −0.081 | 4.00/yr on the sized H; combined nets 0.847 / 0.611 / +0.257 | The trial's figure is the raw H's (§4 item 6) |
| capped nets as one row: NAV tenders 0.814 / 0.576 / 0.219, E1 0.854 / 0.641 / 0.321 | a range, no rescaling cost to the Σ\|Δf\|·G bound (§3); turnover now scaled by its own decision row's f | the rescaling trades were left out. The capped gross figures stand |
| "nothing after 2022-12-30 enters the process" | reworded, and asserted (§2) | `total_returns` reads the full distribution, split and price panels before reindexing. No 2023+ value reached a statistic |
| "E1 lowers the book's net only at 30bp" | at 15bp too (0.6439 against 0.6446) | |
| the JSON's `git_head` db88b14, which did not contain the script | b830366, a clean tree | |

## 7. Files

| file | role |
|---|---|
| `scripts/research/reopen_book/reopen_book.py` | the measurement; its rules in the docstring |
| `scripts/research/reopen_book/extract_trial_series.py` | runs each trial branch's committed code, guarded; builds both return conventions; `check_same_h` |
| `scripts/research/inference.py` | `stationary_bootstrap_indices`, `stationary_bootstrap_corr`, `fisher_corr_ci` |
| `scripts/research/tests/test_inference.py`, `test_reopen_book.py` | the tests, including the three review defects, each failing against b43bf35 |
| `results/research/reopen_book/reopen_book_2026-10-28.json` | every [V] figure, aggregates only |
