# Two accounts as one portfolio: what adds % return on all capital (2026-11-02)

**Report only. Zero trials (CEF stays 53). No spec changed.** This answers the portfolio half of
the team lead's 2026-11-02 question, "what else can we do to mine more alpha and returns, given our
portfolio set-up and two accounts". The objective is the team lead's of 2026-10-30: the **%
return on ALL capital** (`docs/SYSTEM.md` §5, 2026-11-01).

**Labels.**
- **[V]**: computed in this session by the `pm_*.py` script named, in this folder.
- **[doc: path]**: copied from a note and not re-run.
- **[U]**: arithmetic on a stated assumption.

**Window.** Every statistic is fit-only, asserted ≤ 2022-12-30. No 2023+ row was loaded.
- W1 is 2013-06-25 → 2022-12-30, the core's own book.
- W2 is 2005-02-22 → 2022-12-30. On W2 the core before W1 is the house fixed-book proxy at 10
  year-end books.

**Scoring.**
- **Gross is the headline**, price only (PR) first, because that is paper's P&L of record. Total
  return (TR) sits beside it.
- The 5 / 15 / 30bp grid is the real-money view, labelled.
- Borrow is not charged (paper charges none).

**The book as it stands.**
- Core: ×1.13, cap 1.80, account 1, live.
- C4: ×1.27, cap 1.90, account 2, approved but **not armed**.

---

## 0. The answer

| rank | action | Δ gross % on all capital, PR / TR | Δ combined Sharpe, PR / TR | Δ net at 5 / 15 / 30bp (PR) | needs | verdict |
|---:|---|---|---|---|---|---|
| 1 | **Arm C4 at ×1.27** (approved: CEF trials 52, 53) | **+6.0 / +5.4** (W1). At C4's own-window edge about +5.3 PR. At its committed-holdout Sharpe 0.725 about +2.6 [U] | **0.97 → 1.84 / 0.92 → 1.72** | +4.5 / +1.5 / **−3.1**: **flips** between 15 and 30bp | No trial. The team lead's keys, the ruled cap re-derivation against NLV, and arming | **Do first.** Every unarmed session costs about 2bp of all capital |
| 2 | Core up to its own limit, ×1.13 → ×1.29, C4 kept at 1.27 | +0.41 / +0.24 | −0.04 / −0.06 | +0.34 / +0.22 / +0.04: no flip on PR (TR flips at 30bp) | **CEF trial 54**, and an exception to "equal risk per account" (2026-10-29) | **Not now.** The risk falls on the weaker, worse-measured book (§5) |
| 3 | Joint re-split at 5.25%: core 1.09, C4 1.31 | +0.07 / +0.10 | +0.02 / +0.03 | +0.03 / −0.04 / −0.15: **flips** | CEF trial | **No.** On a plateau and inside the noise |
| 4 | C4 starting balance above $100k at its reset ($128k, derived) | +0.29 / +0.14 | +0.05 / +0.03 | +0.15 / **−0.12** / −0.54: **flips** | C4 spec change (`capital_usd`, `max_gross_exposure_usd`); cap re-derivation | **No.** It rests on a Sharpe gap that is not significant (p 0.17–0.28), and it loses net at 15bp |
| 5 | Dynamic risk shifting on relative opportunity | −0.08 … +0.20 (four variants) | −0.01 … +0.07 | +0.09 / −0.12 / −0.44 for the best variant: **flips** | It would need a trial | **Closed at the power gate.** No variant beats its placebo's 95th percentile. P(pass) ≤ 0.05 even at the top of the CI over 9.5 years |
| 6 | Spend a "cross-account factor offset" | none: the factor parts add, not offset | at most +0.04 (an in-sample hedge bound) | — | — | **Nothing to spend.** Factor share of variance is 0.3–3% |

All rows are [V], from `pm_q1_joint.py`, `pm_q2_dynamic.py`, `pm_q4_capacity.py` and
`pm_q5_capital.py`, on the exact build. Row 1 compares against the core alone on $200k, with C4's
$100k idle.

**What binds** (§1.4). Reg T's 2× never binds: both stress caps sit inside it.
- **C4 is held by its stress cap.** Its mean uncapped gross is 1.84 against 1.90. Term (d) stops it
  at ×1.31, and it sits at the cap on 26.9% of W1 sessions.
- **The core is held by neither margin nor its cap.** It is held by the equal-risk ruling, which
  ties its risk to C4's cap. Its own limits are:
  - zero-edge P(KILL) ≤ 5% on the median 2008 book: ×1.30;
  - term (d): ×1.49.
- Live on 11-02 the core held 1.19× against 1.80×, so the vol target binds [doc: the brief, replay
  output].

**Two findings that matter more than any of the rows.** Both are in §3.3.
1. **The fit's core book never held the muni group.**
   - MHD clears the ADV floor on 0% of W1 sessions; MQY clears it only in 2022, on 35% of sessions.
   - The live book is short MQY/MHD, and that cost −$1,849 of NAV in 09-15..10-30
     [doc: `research-live-attribution`].
   - So the core's fit risk, and the trial-53 sizing built on it, do not contain the bet the live
     book carries.
2. **On 56.4% of W1 sessions fewer than `min_names` = 6 names are eligible.**
   - On those sessions the harness holds its last target, while the live sleeve flattens
     [doc: `docs/JOURNAL.md` 2026-11-02].
   - So every core figure here inherits that divergence.

Both argue against putting more risk in the core (row 2) before its 60-session review.

---

## 1. Q1: joint versus separate sizing

### 1.1 The core–C4 correlation, by era [V `pm_q1_joint.py`]

| window | daily ρ TR (95% CI, stationary bootstrap, block 21) | daily ρ PR | unit Sharpe core / C4 (TR) |
|---|---|---|---|
| W1 2013-06 → 2022 | **+0.011** (−0.029, +0.055); block 63: (−0.026, +0.051) | +0.013 | 0.955 / 1.471 |
| W1, 21-session sums (n 115) | +0.103 (−0.115, +0.311) | +0.095 | — |
| 2013-06..2017 | +0.035 | +0.040 | 0.86 / 1.47 |
| 2018–22 | −0.008 | −0.010 | 1.04 / 1.47 |
| H5 2015–19 | +0.032 | +0.034 | 0.84 / 1.21 |
| H5 2020–22 | −0.018 | −0.018 | 1.02 / 1.64 |
| 2005-02..2009, core **proxied** (10 fixed books) | −0.112 / −0.037 / +0.112 (min / median / max) | — | a proxy, not the book |

**Rolling and tail behaviour.**
- The rolling 252-session ρ ranges from −0.10 (2020-02) to +0.17 (2016-11); its median is −0.002.
- On the core's worst 5% of W1 days (−82.8bp mean), C4 averages **+7.5bp**.
- On C4's worst 5% (−73.8bp), the core averages −0.9bp.
- This reproduces the four-sleeve note's +0.011 [doc: `SCRATCH/alloc4/tables/a3_corr.csv`].

**The two accounts are uncorrelated in every era and in both tails.** The combined book already
gets nearly all the diversification two sleeves can give.

### 1.2 The jointly optimal split at the accepted 5.25% [V `pm_q1_joint.py` §2]

The derivation:
- Equal risk reproduces trial 53 exactly: core 1.1357, C4 1.2712.
- The mean-variance risk weights are x ∝ R⁻¹S, on the iso-vol line at 5.25%.

| input Sharpes | C4 risk weight | m core / m C4 | term (d) (C4's mean uncapped gross ≤ 1.90) |
|---|---:|---|---|
| equal risk (the ruling) | 0.500 | 1.136 / 1.271 | holds |
| fit as measured, TR | 0.609 | 0.869 / 1.513 | **fails** |
| fit as measured, PR | 0.624 | 0.829 / 1.541 | **fails** |
| empirical-Bayes shrunk, TR (τ² 0.031) | 0.526 | 1.076 / 1.335 | **fails** |
| empirical-Bayes shrunk, PR (τ² 0.087) | 0.558 | 0.999 / 1.408 | **fails** |
| **constrained optimum: C4 at its term (d)** | **0.517** | **1.097 / 1.313** | at the bound |

**Every mean-variance point wants more C4, and every one breaks C4's cap.**
- The C4 − core Sharpe gap is +0.515 TR (Boot-TS p 0.284, 95% CI −0.37 … +1.40) and +0.614 PR
  (p 0.173) [V].
- It is real enough to tilt toward and not significant.
- Even so, the cap allows only a 1.7-point tilt.

### 1.3 Plateau, and the exact build

**The house cap model along the whole 5.25% line** [V `pm_q1_isovol_2026-11-02.csv`]:
- Between C4 weights 0.475 and 0.525, gross TR is 8.50–8.52% and PR 9.18–9.20%. **That is a
  plateau.**
- On the feasible part (weight ≤ 0.50), the model's argmax *is* equal risk, at 9.20% PR. It is
  named and not chosen.

| exact build (route B), W1 | gross PR %/yr | SR PR | gross TR | SR TR | turn/yr | net PR @ 5 / 15 / 30bp |
|---|---:|---:|---:|---:|---:|---|
| approved 1.13 / 1.27 | **9.65** | 1.840 | 8.75 | 1.724 | 38.0 | +7.75 / +3.95 / −1.75 |
| term-(d) optimum 1.09 / 1.31 | 9.71 | 1.860 | 8.86 | 1.752 | 38.7 | +7.78 / +3.91 / −1.90 |

The approved row reproduces the trial-53 note's 8.76% / 9.65% [doc: PREREG_VOLTARGET §0.A].

**Answer to Q1.**
- **The jointly optimal multipliers do not differ materially from ×1.13 / ×1.27:** +0.07%/yr PR.
- They are on a plateau.
- The gain is inside the noise of the Sharpe gap, and it costs a trial.
- **Keep ×1.13 / ×1.27.**

### 1.4 What binds [V `pm_q1_joint.py` §5, `pm_q4_capacity.py`]

| account | mean uncapped gross at its m | its cap | held at cap (exact, W1) | term (d) limit | term (c) limit: zero-edge P(KILL) ≤ 5% | Reg T 2× |
|---|---:|---:|---:|---:|---:|---|
| core ×1.13 | 1.363 | 1.80 | 19.5% | **×1.49** | **×1.30** (median 2008 book); ×1.56 on W1 | never: the stress cap is inside it |
| C4 ×1.27 | 1.838 | 1.90 | 26.9% | **×1.31** | not reached by ×1.50 | never |

---

## 2. Q2: dynamic risk shifting [V `pm_q2_dynamic.py`]

**The graveyard first.** "Sizing up on |z|" and "sizing up on dislocation" are dead
(`docs/RESEARCH_STATE.md`). This screen is their *relative* form:
- total ex-ante risk is held at 5.25%;
- only the split moves, b₄ = rel_C4 / (rel_core + rel_C4);
- rel is each sleeve's mean |z| (A) or z-dispersion (B), read at t−1 against its own trailing
  252-session mean (data < t);
- it trades through route B with a moving m (`pm_common.band_dyn`, proved equal to the trial-53
  build at constant m).

The rule was declared in the docstring before any result. There are four variants.

| variant (PR) | gross %/yr | SR | turn vs static | active %/yr (NW t) | beats exact placebo (100 circular shifts) | net @ 5 / 15 / 30bp |
|---|---:|---:|---:|---|---:|---|
| static 1.13 / 1.27 | 9.65 | 1.840 | — | — | — | +7.75 / +3.95 / −1.75 |
| absz, daily | 9.57 | 1.829 | +0.3% | −0.08 (−0.46) | 38% | +7.66 / +3.85 / −1.87 |
| disp, daily | 9.63 | 1.843 | +0.3% | −0.01 (−0.08) | 61% | +7.73 / +3.92 / −1.79 |
| absz, monthly | 9.71 | 1.880 | **+5.3%** (outside H2) | +0.07 (+0.34) | 59% | +7.71 / +3.71 / −2.29 |
| disp, monthly | 9.85 | 1.909 | **+5.6%** (outside H2) | +0.20 (+1.07) | 89% | +7.84 / +3.83 / −2.19 |

**Reading the table.**
- The two turnover-matched (daily) variants find nothing.
- The monthly ones trade 5–6% more, so they are not turnover-matched.
- Gross is positive for the best one, but **the sign flips by 15bp**.
- The best of four beats 89% of its placebo; none clears 95%.
- The house cap model disagrees with the exact build on the active return's sign for two variants,
  so the fit cannot even agree with itself here.

**Power** (the active series, desk bar at N = 54, √(2 ln 54) = 2.825; `inference.p_pass_dsr`):
- **P(pass) is 0.000 at every variant's fit IR, over 1, 3 or 9.5 years.**
- At the top of the 95% CI, P(pass) is ≤ 0.002 over three years and ≤ 0.05 over 9.5 years.
- **Closed at the power gate. No trial.**

---

## 3. Q3: cross-account factor offset, and the core's NAV drag [V `pm_q3_factors.py`]

### 3.1 Betas (Dimson, summed; HAC 5; W1)

| account at its m (PR) | equity | credit | rates (term) | muni | loans | R² | factor share of variance |
|---|---:|---:|---:|---:|---:|---:|---:|
| core ×1.13 | −0.008 | +0.041 | **+0.132** (t 1.76 unit) | +0.074 | −0.058 | 0.020 | 0.4% |
| C4 ×1.27 | −0.028 | −0.010 | +0.062 | **−0.084** | −0.018 | 0.022 | 2.7% |
| combined $200k | −0.018 | +0.016 | +0.097 | −0.005 | −0.038 | — | factor vol 0.74%/yr |

**C4 offsets the core on muni and credit, and adds to it on rates, equity and loans.** Net, the
cross term is positive: the two factor parts *add*, by 17–22% of their variance (TR / PR).

**But there is almost nothing to offset.**
- Factor variance is 0.3–3.2% of each account's.
- Alphas are t 3.0 (core) and t 5.1 (C4).
- Hedging every beta at its own in-sample value lifts the combined Sharpe by at most 1.782 → 1.826
  PR (1.706 → 1.748 TR), and the core's falls (0.959 → 0.948).
- **There is no factor risk budget to free and spend elsewhere.**

### 3.2 The core's NAV drag on fit data: noise, not a tilt

The core's price-only P&L, split on the W1 unit book:

| component | %/yr | vol | NW t |
|---|---:|---:|---:|
| price-only P&L | +6.43 | 6.70% | +3.47 |
| **discount component** | **+6.70** | 6.81% | **+3.69** |
| **NAV component** | **−0.27** | 2.48% | **−0.39** |
| of which muni names | −0.07 | 0.46% | −0.24 |
| of which muni, persistent tilt (mean net weight × muni NAV) | −0.01 | 0.07% | −0.49 |

**How to read it.**
- The NAV component is pure noise on the fit, and it is negatively correlated with the discount
  component (−0.23 daily).
- The persistent muni tilt explains 7.1% of the variance of 34-session muni NAV components.
- The fit book's net muni weight averages +0.010. It is zero on 92.6% of sessions.

**The live window placed in the fit's 34-session distribution:**

| component (live, of $100k) | z | percentile | reading |
|---|---:|---:|---|
| discount, +1.58% | +0.34 | 69% | ordinary |
| price-only P&L, −0.98% | −0.88 | 15% | ordinary |
| NAV component, −2.25% | −2.77 | 0.8% | see §3.3 |
| muni NAV, −1.85% | −5.56 | — | meaningless: the fit's reference is nearly empty |

### 3.3 Why the fit cannot answer the live muni loss

**The fit's core book held munis on 7.4% of W1 sessions.**
- MHD never clears the ADV floor on W1. MQY clears it on 35% of 2022 sessions and in no earlier
  year.
- The live book is short MQY and MHD, and lost −$1,849 on their NAVs
  [doc: `research-live-attribution:results/cef/LIVE_ATTRIBUTION_2026-11-02.md`].
- **That bet is outside every fit statistic for the core.** This includes trial 53's vol, its
  drawdown odds and R1–R3's thresholds.

**What the fit can measure is the bet's size per unit of weight.**
- The two muni names' NAV (equal weight) has 6.39%/yr vol.
- Its beta to MUB − rf is 1.37 (t 16.4), with R² 0.64.
- A net muni weight of 0.10 (0.30) of NAV carries a 34-session NAV-leg sd of 0.23% (0.70%). After
  a MUB hedge at that beta it carries 0.14% (0.42%).
- A −1.85% month is about 2σ at a 0.40 muni short. That is consistent with noise on a large bet,
  not with a persistent drift.

**The live muni weight itself is UNMEASURED here** (no broker read).

**What to do with it.** The cross-account answer is that **C4 cannot offset it**: C4 holds no
munis, and its muni beta is −0.08 at t −0.96. A MUB NAV hedge inside the core account is a change
to the live book: a pre-registered CEF trial, which spends no capacity (the core has 0.44 of mean
gross idle). It is not hard muni neutrality (graveyard: 0.97 → 0.82), because it keeps the discount
bet and removes only the NAV leg. Measure the live net muni weight first:
- if it is persistently large, the hedge is worth a pre-registration;
- if it flips with the signal, it is noise and costs only turnover.

The sibling `angle_nav_leg_*` files in this folder are another agent's, on the NAV leg as alpha.
They are not used here.

---

## 4. Q4: idle capacity, and what it costs [V `pm_q4_capacity.py`]

Zero edge decides, using the worst of SB21 / SB63 / GAUSS and the worse of TR and PR. HALVE does
not act. The figures at ×1.13 reproduce the trial-53 note to the digit (core W2 H 7.2 / 15.2 /
51.3%, K 0.4 / 2.4 / 17.4%) [doc: PREREG_VOLTARGET §0.A].

| core m (C4 1.27) | account gross PR (model) | mean uncapped gross | P(HALVE) W1 | P(KILL) W1 | P(HALVE) W2 min / median / max | P(KILL) W2 min / median / max | combined W2 median H / K |
|---:|---:|---:|---:|---:|---|---|---|
| **1.13** | 7.19% | 1.363 | 15.9% | 1.53% | 7.2 / 15.2 / 51.3 | 0.4 / 2.4 / 17.4 | 3.4 / 0.07 |
| 1.20 | 7.55% | 1.448 | 18.9% | 2.15% | 9.4 / 18.3 / 52.2 | 0.6 / 3.3 / 18.1 | 3.9 / 0.10 |
| 1.25 | 7.79% | 1.508 | 20.7% | 2.65% | 10.8 / 20.6 / 52.8 | 0.7 / 3.7 / 18.5 | 4.2 / 0.12 |
| **1.30** | 8.03% | 1.568 | 22.5% | 3.07% | 12.2 / 22.7 / 53.4 | 0.9 / **5.1** / 18.9 | 4.6 / 0.16 |
| 1.50 | 8.75% | 1.810 | 27.7% | 4.69% | 17.0 / 30.1 / 54.9 | 1.7 / 7.6 / 19.9 | 6.3 / 0.29 |

| C4 m (core 1.13) | account gross PR | mean uncapped gross | decided above cap | P(HALVE) / P(KILL) W2 |
|---:|---:|---:|---:|---|
| **1.27** | 11.17% | 1.838 | 47.4% | 16.3% / 1.6% |
| 1.30 | 11.32% | 1.881 | 51.6% | 17.3% / 1.8% |
| 1.50 | 12.04% | 2.171 | 75.3% | 22.4% / 3.0% |

**The limits, derived as crossings of the declared 2026-10-29 terms, not picked:**
- **core:** term (c) on the median 2008 book binds first, at ×1.2977 (written 1.29). Then come
  term (d) at ×1.49 and term (c) on W1 at ×1.56. Zero-edge P(HALVE) on W1 passes 20% at ×1.23.
- **C4:** term (d) at ×1.313; term (c) is not reached.

**Idle capacity is in the core, not in C4:**
- C4 has 3% left (1.27 → 1.31), worth +0.07%/yr.
- The core has 14% (1.13 → 1.29). Exact build: combined +0.41%/yr PR, +0.24%/yr TR. Sharpe
  1.840 → 1.803 PR, 1.724 → 1.663 TR. The core account's maxDD goes from 15.1% to 16.4% PR, and it
  sits at the cap on 22.7% of sessions.

**What it costs per account** (the runner measures drawdown per account), core ×1.13 → ×1.29,
read between the 1.25 and 1.30 rows:
- zero-edge P(HALVE) through 2008 rises from 15.2% to about 22% on the median book;
- P(KILL) rises from 2.4% to about 4.8%;
- on the worst book, P(KILL) stays at about 19% at any multiplier. The worst books are the
  2017-12-29 and 2019-12-31 ones at 1.70–1.80 gross, held through 2008 [doc: PREREG_VOLTARGET §5.3].

**Return keeps rising with m:** about +0.24%/yr of combined PR per 0.1 of core m. So there is no
plateau to land on. The limit is a constraint, not an optimum.

---

## 5. What I am giving up, what would change my mind, the downside

**Giving up**:
- about +0.4%/yr PR from the core's idle capacity;
- about +0.3%/yr PR from a C4 capital tilt;
- about +0.1%/yr from a joint re-split.

That is roughly 0.8%/yr of fit-path gross, kept off the book because each piece either:
- puts risk in the account whose fit is least like its live book (§3.3, and the 56.4%
  thin-session divergence); or
- rests on a Sharpe gap that is not significant; or
- flips sign by 15bp.

**What would change my mind**, each re-measured on its read date (H14), never keyed on a figure
here:
1. **The core's 60-session review passes, and R3 (realised vol) sits near the model's.** Then
   raising the core to its term-(c) limit is a fair trial: CEF 54, pre-registered, with the
   equal-risk exception ruled.
   - If live vol runs above the model's (the unmeasured muni bet), the opposite follows: the
     core's multiplier should come *down*.
2. **A live record in which C4's Sharpe exceeds the core's by a margin its own sampling error
   cannot explain.** Then the capital tilt of row 4 (derived C4 balance about $128k) is worth its
   spec change. Until then equal capital is the robust choice.
3. **Portfolio Margin, or a pooled cap.** C4's binding constraint is its own 1.90 cap. Pooling it
   with the core's idle 0.44 of gross is what would let C4's higher fit Sharpe be used. The team
   lead declined C4 inside the core's account (2026-11-02); that remains the structural fix.

**Downside if I am wrong.** If the core's edge is as good as the fit says, holding it at ×1.13
forgoes about 0.4%/yr. If C4's edge is at its committed holdout's 0.725 rather than the fit's,
then:
- arming it still adds about +2.6%/yr gross on all capital [U];
- on the real-money grid at 30bp it subtracts. C4 is paper-only by ruling (2026-10-19).

---

## 6. Reproduce

`SCRATCH` is this session's scratch folder. It holds the trial-53 series:
- `alloc_review/core_trpr.parquet`;
- `alloc4/series/c4spec_*` and `core_proxy_*`;
- `alloc4/declared_threshold.json`.

C4's inputs are CRSP-derived. They are written to `SCRATCH/pm/c4` and never to a tracked file.
`W4CACHE` is the gitignored W4 cache (`ff5_umd_daily.parquet`, `crsp_dsf_w4.parquet`).

```bash
python3 -I results/cef/screens_2026-11-02/pm_c4_extract.py --scratch SCRATCH --c4-tree WORKTREES/c4-step2-spec  # C4 T, R, z aggregates (13 s)
python3 results/cef/screens_2026-11-02/pm_q1_joint.py    --scratch SCRATCH                        # §1 (3 s)
python3 results/cef/screens_2026-11-02/pm_q2_dynamic.py  --scratch SCRATCH                        # §2 (90 s)
python3 results/cef/screens_2026-11-02/pm_q3_factors.py  --scratch SCRATCH --factor-cache W4CACHE # §3 (5 s)
python3 results/cef/screens_2026-11-02/pm_q4_capacity.py --scratch SCRATCH                        # §4 (about 10 min)
python3 results/cef/screens_2026-11-02/pm_q5_capital.py  --scratch SCRATCH                        # row 4 (3 s; reads pm_q1's json)
```

**Gates.** Each script raises unless both of these reproduce to 1e-12:
- the core unit book reproduces `alloc_review/core_trpr` (it does, to 0.0);
- C4's spec book reproduces `alloc4/series/c4spec_H` and `c4spec_trpr` (to 0.0).

**Outputs:** `pm_q*_2026-11-02.json`, `pm_q*_output_2026-11-02.txt` and
`pm_q1_isovol_2026-11-02.csv` in this folder.

**Panels' last dates** (all read with a filter at 2022-12-30):
- core `cef_prices` and `cef_nav` to 2022-12-30, `cef_distributions` to 2022-12-28, no splits;
- C4 families prices and NAV to 2022-12-30, actions to 2022-12-29;
- CRSP dsf to 2022-12-30;
- French (vintage 202608) used to 2022-12-30.

**Code:**
- this tree at origin/main 862b1d0 (core spec `cef_discount.v8.20261101`: band 0.048, cap 1.80);
- C4 at `c4-step2-spec` 6f62527, asserted clean, and its spec from `c4-integrate`
  (`c4_families.v1.20261029`: band 0.048, cap 1.90).
