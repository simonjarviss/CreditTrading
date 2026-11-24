# XASSET slate — results: all four tests fail; no sleeve

**Pre-registration** `results/xasset/PREREG_XASSET_SLATE_2026-10-12.md`,
revision 3, approved 2026-10-14 with X5 withdrawn (N = 4), plus the team
lead's amendment block of 2026-10-14 · **Bar** `validate._dsr` > 0.95 at
N = 4; slate bar √(2 ln 4) = 1.665 · **Counter** XASSET **4 of 4**
(trials 1–4: X1, X3, X2, X4, in run order) · **Branch** `trial-xasset` ·
**Panel** the Stage 0a ETF panel, SHA-256 `b843f558…`, with CRSP to
2024-12-31, yfinance to 2026-07-20 and Alpaca to 2026-10-13. The fit uses
CRSP only; the holdout ends 2026-09-30. Fit run 2026-10-14; X2's and X4's
holdouts opened 2026-10-15 UTC.

**Reproduce.** Pins and inputs: `python3 scripts/xasset/stage0a.py`
(`results/xasset/STAGE0A_2026-10-14.md`). Each test:
`python3 scripts/xasset/x1_credit_trend.py --trial 1`, `x3_month_end.py --trial 2`,
`x2_rebalancing.py --trial 3`, `x4_multi_trend.py --trial 4`, then
`--holdout` for each. They refuse to rerun, because each test runs once. The
figures are in `results/xasset/trials/x<k>_{fit,holdout}_2026-10-14.json`, with
stdout in `results/xasset/runs/`. **Every figure below is [V]: produced by
those scripts on 2026-10-14/15 from the pinned inputs.**

## The verdicts

| test | verdict | deciding rule (the first that failed) | D-code |
|---|---|---|---|
| **X1** credit and rates trend | **FAIL** | stage 1: NW t(21) 1.62 < 1.96 | **D1** |
| **X2** rebalancing front-run | **FAIL** | stage 1: NW t(21) 1.59 < 1.96 | **D1** |
| **X3** month-end Treasury | **FAIL** | stage 4: TERM β 0.340 and 0.329 > 0.10, although alpha t 4.54 and 4.30 ≥ 3 | **D4** (and D2 at 15bp) |
| **X4** multi-asset trend | **FAIL** | stage 2: TSH beats it net at 5/15/30bp | **D4** (the historical-mean rule) |

**No test passes, so no sleeve and no frozen-spec key follows** (plan §4).
Every stage was computed for every test whatever the verdict, as declared.

## Decision statistics: sized, uncapped sleeve, fit P&L window to 2022-12-30

| | X1 | X2 | X3 | X4 |
|---|---|---|---|---|
| P&L window (T) | 2008-05-02 → (3,693) | 2002-09-04 → (5,118) | 2002-09-04 → (5,118) | 2005-12-02 → (4,299) |
| k (P5) | 0.197 | 0.611 | 2.424 | 0.256 |
| **gross Sharpe** | **0.41** | **0.33** | **1.04** | **0.45** |
| NW t (L = 21); automatic lag | 1.62; 1.56 (L 8) | 1.59; 1.65 (L 9) | 4.94; 4.83 (L 9) | 1.964; 1.92 (L 9) |
| stationary-bootstrap 95% CI, Sharpe | −0.09 … 1.04 | −0.08 … 0.71 | 0.64 … 1.44 | 0.00 … 0.94 |
| stage 2: named control | TSH: gross 0.40, nets 0.39 / 0.36 / 0.33. **Fails**: X1 loses net at every cost | BIL/SHY Sharpe 0.18 vs X2's 0.33 on 2007-05-31 →. **Fails** (≥ ½) | IEF on other sessions −0.05. Passes | TSH: gross 0.45, nets 0.44 / 0.41 / 0.38. **Fails** |
| stage 3: placebo p95 (span); shift(3) | 0.78 (from 2011-03-04); 0.45. **Fails** | 0.27; −0.04 (reported). Passes | 0.62; 0.60 (reported). Passes | 0.77 (from 2011-03-04); 0.47. **Fails** |
| stage 4 R-D4: alpha %/yr (t) | 1.44 (0.79) | 1.25 (0.99) / 1.32 (0.83) | 5.33 (4.54) / 5.86 (4.30) | 1.52 (1.00) / 1.68 (1.06) |
| R-D4 betas (OLS; largest in bold) | MKT 0.08, **TERM 0.17**, HY −0.07, IG 0.00 | MKT 0.07, TERM 0.04 / **IG 0.11**, MKT 0.06 | **TERM 0.34**, MKT 0.01 / **TERM 0.33**, IG −0.10, MKT 0.03 | **TERM 0.12**, GOLD 0.05 / TERM 0.09, HY −0.07, MKT 0.06 |
| stage 5: `_dsr` at N = 4 | 0.470 | 0.433 | **0.999** | 0.580 |
| beside it: SR·√yr vs 1.665; `_dsr` at N = 162 | 1.59; 0.06 | 1.50; 0.04 | 4.67; 0.94 | 1.87; 0.10 |

- Where two cells are separated by a slash, they are the two declared R-D4
  regressions: the full fit, then from 2007-04-12.
- VIFs and HAC 95% CIs for every β are in the JSONs. The largest VIF is 3.8
  (HY).
- X3's TERM β has a CI of 0.29 … 0.39. That is the D4 kill PREREG §6 stated
  in advance.

## Gross headline with the cost grid (net Sharpe; turnover = Σ|ΔH|/yr, sized)

| | gross | turn/yr | 5bp | 15bp | 30bp | flips sign? | tradable (capped) gross |
|---|---:|---:|---:|---:|---:|---|---:|
| X1 | 0.41 | 3.6 | 0.38 | 0.32 | 0.23 | no | 0.42 (cap binds 12.0%) |
| X2 | 0.33 | 56.8 | −0.14 | −1.09 | −2.51 | **yes** | 0.33 (never binds) |
| X3 | 1.04 | 58.3 | 0.55 | −0.42 | −1.88 | **yes** | 1.04 (binds 14.3%: every window day) |
| X4 | 0.45 | 3.9 | 0.42 | 0.36 | 0.26 | no | 0.46 (binds 10.3%) |

**Borrow is charged separately and is UNMEASURED.** The repo holds no ETF
borrow history. Mean short notional of the sized sleeve, as a fraction of
capital: X1 0.22, X2 0.16, X3 0, X4 0.30. Any rate can be applied to those.

## Eras (H5), gross Sharpe, sized; turnover sd/mean across eras

| | 2005–09 | 2010–14 | 2015–19 | 2020–22 | sd/mean |
|---|---:|---:|---:|---:|---:|
| X1 (from 2008-05) | 0.82 | 0.88 | 0.25 | 0.02 | 0.32 |
| X2 | 0.90 | 0.21 | 0.08 | −0.38 | 0.08 |
| X3 | 0.87 | 1.28 | 1.37 | 1.04 | 0.00 |
| X4 | 0.62 | 0.84 | 0.22 | 0.11 | 0.25 |

X1, X2 and X4 decay across the eras. X3 does not.

## Holdouts (2023-01-03 → 2026-09-30, 939 sessions; each opened once, k frozen)

| | mean %/yr | Sharpe (95% CI) | NW t | sign as fit | stage 7 |
|---|---:|---|---:|---|---|
| X1 | −1.41 | −0.39 (−1.33 … 0.58) | −0.73 | **no** | reported only |
| X2 | 0.75 | 0.25 (−0.88 … 1.33) | 0.45 | yes | reported only |
| X3 | 3.23 | 0.59 (−0.36 … 1.51) | 1.27 | yes | reported only |
| X4 | 0.86 | 0.19 (−0.70 … 1.10) | 0.39 | yes | reported only |

- **The holdout cannot rescue a failed fit** (§1.5). The sign rule applies
  only to a fit PASS-candidate, and there was none.
- **The fit rows of each continuous series reproduced the fit P&L bit for
  bit.**
- **Two regime rows:**
  - X3 under T+1 (from 2024-05-28): Sharpe 0.44;
  - X2 after the paper's sample (from 2023-03-18): 0.22.

## Reported rows that do not decide

- **R-AQR (monthly).**
  - X1 loads on TSMOM^FI (β 0.075, t 5.2), alpha t 0.65.
  - X4 loads on TSMOM (β 0.25, t 5.3), alpha t 1.24.
  - X3's alpha survives TSMOM^FI: 5.5%/yr, t 4.6.
- **R-LONG.**
  - X1 on its long-only version: β 0.53, alpha t 0.88.
  - X4: β 0.44, alpha t 1.15.
- **R-Q (flagged sessions excluded).**
  - X1's Sharpe rises to 0.99 and X4's to 0.80. The excluded sessions
    include March 2020: X1 lost 8.1% on 2020-03-18 (PFF −17.0%).
  - X3: 1.05; X2: 0.35.
- **In-house source in place of CRSP:** within 0.01 of every headline.
- **Leave-one-out.**
  - X1: 0.36 – 0.46.
  - X4: 0.42 – 0.49.
- **The 21 refresh offsets.**
  - X1: 0.04 – 0.55 (median 0.38).
  - X4: 0.06 – 0.49 (median 0.36).
- **X2's diagnostics.**
  - The Calendar part has Sharpe 0.32; its mid-month placebo window, 0.01.
  - The Calendar part's real Sharpe is above 98.5% of its month-sign
    permutations.
  - Daily correlation with X3: −0.01. Alpha of the week4 component on X3:
    t 1.68.
- **Correlation with the CEF book (P12).**

  | row | daily ρ (X1 / X2 / X3 / X4) |
  |---|---|
  | fit, 2013-06-21 → 2022-12-30 | 0.12 / 0.01 / −0.05 / 0.10 |
  | holdout, to 2026-09-25 (the CEF panels' last common date; §1.10 stops the row at the panel end) | 0.06 / 0.04 / 0.00 / 0.08 |

  21-session and HY-stress figures are in the JSONs.
- **Capacity** (1% of 63-session median dollar volume on a median rebalance
  day): X1 about $5.7m, X4 about $5.1m, X2 about $17m, X3 about $0.3m. X3's
  figure is held down by IEF's thin early-2000s volume. [U reading of "median
  rebalance day", see below]

## What this means

- **None of the four cross-asset sleeves clears the slate.** X1, X2 and X4
  show no detectable edge at the pre-registered strength. Their fit Sharpes
  (0.33–0.45) sit inside the draft's own expected ranges, where §2.2 put
  P(pass) at 0.04–0.17, so the fails were the expected outcome.
- **X1 and X4 are explained by published trend and its long bias.** They are
  spanned by AQR's TSMOM factors, and the inception-to-date sign does as well
  net of costs.
- **X3 is the one real effect.** The month-end Treasury premium is large,
  stable by era, survives its IEF-on-other-days control and the placebo, and
  clears the deflated bar (0.999). But it is TERM exposure in a part-time
  wrapper (β 0.34). At 58 turns a year it is negative net at 15bp. **A
  TERM-hedged X3 would be a new, separately declared trial** (§6). That is
  the team lead's call, not run here.
- **The CEF desk loses no candidate, and the graveyard gains four entries.**

## The record of this run

- **2026-10-14, Stage 0a** (`856d4bb`): spec pin, DG1–DG3 and Q1–Q7.
- **The run then stopped on two questions, and the team lead ruled the same
  day** (amendment block in the pre-registration, `27e7055`, committed before
  any Stage 0b):
  - **DG1** clears with the yfinance leg within 0.01bp;
  - **the placebo** shuffles only inside the span where every fund trades;
  - **three readings confirmed:** MUB in S_t when flat, the `ewm().var()`
    default bias correction, and turnover as `evaluate()` defines it.
- **Fixed before any run:**
  - TSMOM's NaN 12-month return, which would have shorted PFF in X4;
  - the findings of an independent pre-run review.
- **Fixed after a verdict was written, reported rows only:**
  - R-AQR's monthly date labels;
  - capacity, which now counts only traded names.

  The recovery path rebuilt each decision series and asserted that it was
  bit-identical, so neither fix could change a decision.
- **Process slip, recorded in `37e89ec`.** The counter commit `7357b56` was
  made while one synthetic test, which read real repo state, was failing.
  The trial code was not at fault.

## Readings applied to reported rows only ([U]; never deciding)

| row | reading |
|---|---|
| Q2 stale price | three or more sessions sharing one close |
| R-AQR | calendar months wholly inside the P&L window |
| refresh offsets | a daily TSMOM target over (s, t], s = the last session on or before t − 12 months; `calendar_offset(·, 21, o)` |
| leave-one-out | the same first decision and window; 1/S_t over the remaining names |
| X4 asset classes | credit and rates = X1's nine; equity SPY EFA EEM; commodity GLD DBC |
| X2 mid-month window | the week4 rule at sessions 6–10 in paper time (H rows 5–9) |
| X2 sign permutations | month blocks E−5 … E reassigned across months |
| capacity | the median across rebalance days of the largest traded name's \|ΔH\| / DV63 |
| X2 in-house row | the portfolios start at the close before the in-house first common return |

X4's stage-2 rule text in its JSON reads "X1 beats TSH" because the shared
function's label is X1's. The rule applied was X4 against TSH on X4's
universe.
