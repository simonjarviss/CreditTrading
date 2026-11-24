# Pre-registration — the XASSET slate: five cross-asset tests, declared before any runs

**Date** 2026-10-12 (revisions 1 and 2); **revision 3, 2026-10-13** ·
**Counter** XASSET, a declared slate of **N = 5** (one trial per test, spent
when that test's Stage 0b begins) · **Pass bar** `validate._dsr` > 0.95 at
N = 5 · **Gate** G8 of `results/cef/RESEARCH_PLAN_2026-10-09.md` · **Author**
research agent, branches `research-xasset-slate` (revisions 1–2) and
`fix-xasset-review` (revision 3)

> **Status: APPROVED by the team lead, 2026-10-14, revision 3, with X5
> withdrawn: N = 4.**
>
> - **X5 is withdrawn before any data step.** X5 is cross-sectional
>   fixed-income momentum (§8). Its §2.2 power at the draft's own expected
>   Sharpes was P(pass) < 0.03. That is a forecast from stated priors, not
>   from any return: no Stage 0a step had run.
> - **What N = 4 changes.** §8 is never run. Every "N = 5" elsewhere in this
>   document now reads N = 4. Ruling 1 ("all five tests") is amended to
>   X1–X4. The slate bar becomes √(2 ln 4) = 1.665. `validate._dsr` is
>   evaluated at N = 4.
> - **Unchanged.** Everything else in revision 3 stands, including that the
>   counter moves per test when its Stage 0b begins (§0.2 item 3) and the
>   fixed holdout end of 2026-09-30.
>
> **Team lead, 2026-10-14: three rulings, recorded before any Stage 0b.** The
> run stopped at the end of Stage 0a on two questions and asked to confirm
> three readings (`results/xasset/STAGE0A_2026-10-14.md` §2;
> `results/xasset/XASSET_RESULTS_2026-10-14.md`). No X-test return had been
> combined into a P&L.
>
> 1. **DG1 clears as measured.**
>    - In the yfinance leg, "rebuild unchanged in every existing column" reads
>      as unchanged within **0.01bp**. Against `data/etf_daily.parquet`, the
>      measured maximum was 0.0074bp, on 3,210 `ret_total` cells, all inside
>      the holdout. It is Yahoo's re-basing of Adj Close, which no rebuild can
>      reproduce bitwise.
>    - The fit's CRSP leg is identical.
>    - The Stage 0a panel hash (`STAGE0A_MANIFEST_2026-10-14.json`, SHA-256
>      `b843f558…`) fixes exactly which data every test uses.
>    - In code: `protocol.DG1_RULING`.
> 2. **The block-shuffled placebo (§1.8) shuffles only inside the span where
>    every fund in the test trades**, so no placebo position lands on a date
>    before its fund's first return.
>    - *How it is applied:* only the rows of the sized H dated on or after the
>      latest first return among the test's funds are permuted, in 21-session
>      blocks anchored there. Earlier rows keep their dates.
>    - The placebo Sharpe, like every statistic, stays on the declared P&L
>      window (§1.6).
>    - The span starts at 2011-03-04 for X1 and X4 (BKLN's first return).
>    - For X2 and X3 it starts before the first decision, so their whole H is
>      shuffled, as before.
>    - In code: `protocol.PLACEBO_PRE_INCEPTION_RULE = "span"`.
> 3. **Three readings are confirmed as declared readings:**
>    - (a) MUB counts in the equal-weight denominator S_t when its position is
>      flat (X1, X4);
>    - (b) the ex-ante variance keeps pandas `ewm(com=60, adjust=True).var()`'s
>      default bias correction;
>    - (c) turnover is as `band_frontier.evaluate()` defines it: Σ|ΔH| on the
>      rows inside the window, so the first decision's entry trade is not
>      charged.
>
> Nothing else in revision 3 changes.
>
> *Was:* Status: DRAFT, revision 3 — awaiting the team lead's final approval.
> Revision 3 applies the fixes of an adversarial review (the block below). It
> keeps the team lead's four rulings of 2026-10-12 (§0.1) unchanged, with their
> institutional-rigour requirements. It specifies the data, inference,
> regressions, controls, robustness, holdout and decision order of every test
> before any of their data is touched.
>
> **Nothing has run.** No strategy return, Sharpe, IC, turnover or backtest of
> any X-test was computed to write this. The only measurements are coverage and
> quality counts of the input series, history start dates, the Alpaca asset
> flags of 2026-10-12, the reachability of the factor files, CRSP no-closing-
> trade counts for the panel's 13 built tickers, the frozen spec's hash, session
> counts on the calendar, and arithmetic on the bar and its power
> (`python3 scripts/xasset/slate_feasibility.py [--alpaca --crsp --factors]`;
> the bar and power block re-run 2026-10-13). This commit moves no counter
> (XASSET stays 0), changes no spec and touches nothing on the order path.

---

## Revision 3 (2026-10-13): the adversarial review's fixes

An adversarial review of revision 2 (commit `af61e28`), delivered 2026-10-13,
returned **APPROVE AFTER FIXES**: one critical, three high, four medium and one
low finding. Every fix is applied below as text. None needed a return: the new
figures are calendar counts, the spec file's hash, a CRSP count, and power
arithmetic. The line numbers are `af61e28`'s. §0.1's rulings are unchanged.

| # | severity | the finding (af61e28 line) | what revision 3 does | where |
|---|---|---|---|---|
| 1 | **critical** | **Stage 0 saw the P&L but spent no trial** (l.331, l.123, l.174–176). k = vol_target / σ_fit needs the raw sleeve's whole fit-window P&L, and Stage 0 also allowed a "vendor defect" fix and re-run with no criteria. A run could look at P&L, repair, and re-run for free | Stage 0 is split. **0a** (zero-trial): DG1–DG3, Q1–Q7 and any repair, the only repair being a `BAD_PRINTS`-type stub print confirmed by a third source. 0a ends by committing the panel's hash. **The counter then moves.** **0b** computes k, turnover, gross and the cap-binding share. After 0a nothing is repaired, dropped or substituted. A gate that cannot clear leaves the test UNRUN, and N stays 5 | §0 rule 3; §1.1; §1.11 |
| 2 | high | **k uses future data, and the gross cap carried it into the decision statistics** (§1.3). Whether the 1.80 cap binds on a day depends on k, a fit-window constant; X3 is capped on every window day when IEF's volatility is below 8.8%/yr | Stages 1–3 and 5 are computed on the **sized, uncapped** sleeve, whose scale-free statistics do not depend on k. D4's betas are measured on the sized sleeve. The tradable sleeve is a reported row. Applied to stages 7 and 8 as well, so one series decides throughout (§11 item 4) | §1.3; §1.4–§1.11; §6 |
| 3 | high | **X2's control had the wrong sign** (l.30, l.642). "The same w on SHY − BIL" put SHY in SPY's slot, so its duration sign was the opposite of X2's | H = {BIL: +w, SHY: −w}, so the control's duration sign matches X2's IEF leg. KILL if the control's Sharpe ≥ ½ × X2's, both computed from BIL's first return to 2022-12-30. The alpha of X2's week4 component on X3's sleeve is reported | §0; §3; §5 |
| 4 | high | **The spec was read at run time** (l.176): a spec change between approval and run would change the trial silently | `vol_target_annual` = 0.06, `max_gross_stress` = 1.80 and the spec file's SHA-256 are pinned at approval. The run reads them through `spec.py` and halts at 0a on any mismatch | §1.3 |
| 5 | medium | **The holdout end was free** (l.225): "the primary panel's last date at run time" let the run date set its length | The holdout ends **2026-09-30** for all five tests. No holdout opens until all five fit verdicts are committed | §1.5; §1.11; §10 |
| 6 | medium | **Two undeclared choices in X2** (l.591, l.611): where the Threshold portfolios start, and which sessions each Calendar component earns | Each Threshold portfolio starts at 60% at the close of 2002-07-29 (IEF's first CRSP return [V]). The week4 component earns E−3 … D1 and the Calendar₋₄ component earns D2. A declared reading [U]; the alternative is not run | §5 |
| 7 | medium | **Collinear factors in D4** (l.267–272): INTL = EFA − r_f and EM = EEM − r_f are largely MKT again | INTL = EFA − SPY and EM = EEM − SPY. The \|β\| rule applies to OLS point estimates. VIFs and HAC 95% CIs are printed. No factor is re-specified, orthogonalised or dropped after the result, and a TERM-hedged X3 is a new trial | §1.7; §6; §7 |
| 8 | medium | **Power overstated** (l.440–443, l.870). X2's 0.94 was at HMM's in-sample 1.11 with no delay; X4's 0.73 at a many-market composite; the D4 column used the full fit where the post-2007 regression binds (needed IR 0.76, not 0.67); the β leg was missing | §2.2 and §9 restated at the draft's own expected Sharpes, every figure recomputed with `_dsr` [V]: X2 at 0.2 / 0.5 / 0.8 passes with P = 0.006 / 0.118 / 0.566. Published figures are upper references only. The D4 column uses the binding window and states the β leg. "A fail is informative for X2" is deleted | §1.6; §2.2; §9; `slate_feasibility.py` |
| 9 | low | (a) X5's ladder had no declared window or breadth, and no H2 statement; (b) `_dsr`'s skew and kurtosis inputs were not pinned; (c) the P&L window was not pinned, and `evaluate()['gross_sr']` averages over the flat sessions before the first decision; (d) DG1 would have put the signed `prc` in `prc_adj`, which `src/backtest/engine.py` reads, and checked 10 of the 13 built tickers | (a) breadth ⌈5/2⌉ = 3, X5's window, the H2 reason; (b) sk = `pd.Series.skew()`, ku = `.kurt() + 3`, as `scripts/cef/validate.py:342`; (c) every statistic and T on the P&L from the first decision + 2 sessions to 2022-12-30, never `evaluate()['gross_sr']`, the holdout P&L sliced from the continuous series; (d) a new column, and all 13 rebuild unchanged | §1.1; §1.5; §1.6; §8 |

**Also corrected in place.** Revision 2's §2.2 counted fit sessions from the
first decision + 1; the P&L starts at + 2, so every T falls by one. Its power
used SE = 1/√years; it now uses `_dsr`'s own denominator. Neither moves a
required Sharpe by more than 0.01.

**Decisions this revision leaves to the team lead** are listed in §11.

---

## 0. The declaration

| id | test | traded instruments | published rule (`docs/REFERENCES.md` §12i) | named control | plan |
|---|---|---|---|---|---|
| **X1** | credit and rates trend | HYG LQD IEF TLT EMB PFF MUB BKLN CWB | Moskowitz, Ooi & Pedersen (2012), "MOP": time-series momentum (TSMOM) | Huang, Li, Wang & Zhou (2020), "HLWZ": the historical-mean rule (TSH), same weights | §3 row 3 |
| **X2** | front-running pension and balanced-fund rebalancing | SPY vs IEF | Harvey, Mazzoleni & Melone (2026), "HMM": Threshold + Calendar strategy | the same w on BIL (in SPY's slot) and SHY (in IEF's slot): {BIL: +w, SHY: −w} (revision 3) | §3 row 4 |
| **X3** | month-end Treasury extension | IEF | Hartley & Schwarz (2019), "H&S": long the last 3 sessions | IEF on every other session; IEF held every day | §3 row 12 |
| **X4** | multi-asset trend | X1 + SPY EFA EEM GLD DBC | MOP TSMOM, as X1 | TSH, as X1 | §3 row 12 |
| **X5** | cross-sectional fixed-income momentum | X1 less MUB (8 names) | Baltussen, Swinkels & van Vliet (2019), "BSV", after Asness, Moskowitz & Pedersen (2013), "AMP" | the identical rule on the Treasury ladder SHY IEI IEF TLH TLT; spanning by X1 | §3 row 12 |

**Rules of the declaration:**

1. **N = 5 is fixed on approval** (ruling 1). Every test is judged at N = 5,
   whatever order they run in and whether or not all of them run. Dropping a
   declared test after seeing a sibling's result would be a selection, so N
   never shrinks.
2. **Every parameter is the paper's**, quoted with its page in each test's
   table and in `docs/REFERENCES.md` §12i. Where a futures or index rule cannot
   be applied verbatim to ETFs, the mapping is stated here once, before any
   return is seen, and it is not revisited. One reading is declared where a
   paper is ambiguous (X2's Calendar₋₄; since revision 3 also X2's exposure
   days and its Threshold start). **Nothing was chosen by looking at our data,
   and nothing is swept.**
3. **The counter moves when a test's Stage 0b begins, not at approval**
   (revision 3; before it, "when a test runs"). Stage 0a, which touches no P&L,
   is zero-trial and ends with a commit of the input files' hashes. XASSET's
   trials-used column then goes k−1 → k in a commit made before that test's
   Stage 0b computes anything. A test whose Stage 0a gate cannot clear is
   **UNRUN**: it spends no trial, and **N stays 5**.
4. **Approval approves a test, not a sleeve.** A test that passes goes through
   plan §4: a frozen-spec key with a byte-for-byte no-op proof, its H11
   statistic, then a release.
5. **The plan's one-line summaries give way to the papers.** X1 in plan §3
   reads "252-day excess return ÷ 63-day vol; refreshed every 21 days". The
   paper's parameters, used here, are:
   - 12 calendar months, not 252 days;
   - an exponentially weighted volatility with a 60-day centre of mass, not 63
     days;
   - a refresh at each month-end, not every 21 days.

   X2's "SPY vs IEF/TLT" becomes SPY vs IEF, because the paper's bond leg is
   the 10-year note.

### 0.1 Team-lead rulings, 2026-10-12 (relayed by the coordinator; recorded here as decided)

| # | ruling | how this draft applies it |
|---|---|---|
| 1 | **All five tests run; N = 5.** "Do all 5, but make the tests with institutional rigour, statistical significance, regression, clean data etc. act as a quant researcher" | All five are declared, with a common protocol (§1) and a decision table per test (§4–§8). Revision 1 proposed cutting X3 and X5; that proposal is **withdrawn**. §9 keeps the power arithmetic, so a null result can be read |
| 2 | **The pass threshold is `validate._dsr` > 0.95 at N = 5.** The agenda's reading, SR·√years ≥ √(2 ln 5) = 1.794, is printed beside it, labelled, and never used to decide | P8 (§1.6) |
| 3 | **Correlation with the CEF book is reported, never a kill** (daily, non-overlapping 21-session, and HY-stress windows) | P12 (§1.10). Revision 1's proposed ρ ≥ 0.5 rule is **withdrawn** |
| 4 | **D4 applies with each sleeve sized to the spec's vol target**, read through `scripts/cef/spec.py`, by a sizing rule fixed in advance. The test is then \|β\| ≤ 0.10 and alpha t ≥ 3.0 | The sizing rule is P5 (§1.3). The D4 factor sets are in §1.7 and each test's section |

---

## 1. Common protocol (every test, unless its section says otherwise)

### 1.1 Data (P1–P2)

**P1. Sources, in a declared order.**

- **Primary: CRSP `dsf.ret` for all 19 instruments through 2024-12-31.** It is
  the total return, with every distribution on its ex-date and splits handled
  by CRSP's factors. It is read through `data/etf_daily.parquet`, built by
  `scripts/build_etf_daily.py`.
- **After 2024-12-31:** that build's spliced legs, yfinance to 2026-07-20 and
  Alpaca SIP bars after (REFERENCES §8).
- **Why CRSP comes first.** It is the research-grade record of distributions.
  The yfinance-sourced CEF distribution panel was measured missing 11 CRSP
  distributions, three of them large year-end specials (REFERENCES §8, the W4
  row).
- **Independent cross-check:** the in-house panels `data/rv/etf_panel.parquet`
  and `data/rv/etf_ohlc_extended.parquet`. Their total return is (close +
  distribution) / previous close − 1, from yfinance to each fetcher's
  `YF_LAST` and Alpaca after. The two sources are never averaged. CRSP is
  declared primary now, so neither is picked after a result.

**Data gates before any run (Stage 0a).** All are zero-trial, and each halts
the run if it fails. A gate that cannot clear leaves every test that needs it
UNRUN (§1.11).

| gate | what | done when |
|---|---|---|
| **DG1** | Extend `scripts/build_etf_daily.py` to the nine slate names it lacks, with their PERMNOs (share code 73, resolved from CRSP on 2026-10-12): SPY 84398, EMB 92491, PFF 91874, MUB 92273, BKLN 12631, CWB 92914, IEI 91705, TLH 91704, AGG 89848. Keep the sign of CRSP `prc`, the no-closing-trade flag, **in a new column** (revision 3). `prc_adj` stays \|prc\| / cfacpr, because `src/backtest/engine.py` and `ops/common.py`'s replay read `data/etf_daily.parquet`. Build to a staging path outside `data/` first | every name passes the build's own gates, including its 2024 overlap gate `SPLICE_MAX_BP` (5bp). **All 13 tickers already built** (ANGL, BIL, DBC, EEM, EFA, FALN, GLD, HYG, IEF, JNK, LQD, SHY, TLT) rebuild unchanged in every existing column (`scripts/rv/panel_identity.py`). ANGL, FALN and JNK carry the 69 negative-`prc` rows (30, 38 and 1 [V: `dsf` on the R2 mirror, 2026-10-13; the build's docstring gives the same]; the other ten have none), so the new column is checked on them. Revision 2 named only ten |
| **DG2** | `scripts/data/fetch_aqr_factors.py` (AQR TSMOM and VME files) writes to a gitignored cache and records the file's vintage. French factors come from the existing `scripts/data/fetch_ff_factors.py` | the factor files parse with the columns in §2.1, and REFERENCES carries a row for the fetcher |
| **DG3** | Risk-free: FRED DGS3MO via `scripts/gamma/fetch_fred.py DGS3MO --out <cache outside data/>` (REFERENCES §8) | the series covers the panel's last date minus one session |

**P2. The data-quality screen** runs at Stage 0a on the primary return of every
instrument, over fit and holdout. Every flag is listed in the run's log and its
committed result note, by instrument and date, with both sources' values.
**Nothing is dropped, filled or altered by a trial script.**

| check | rule | action |
|---|---|---|
| Q1 missing | a session inside an instrument's live range with no return (H15) | **halt** |
| Q2 stale price | ≥ 3 consecutive sessions with an unchanged raw close | flag |
| Q3 zero volume | CRSP `vol` = 0, or zero volume in the spliced legs | flag |
| Q4 no closing trade | CRSP `prc` < 0, a bid/ask midpoint | flag |
| Q5 outlier | robust z > 10, with z = \|r − median₂₅₂\| / (1.4826·MAD₂₅₂) over the 252 sessions through t−1; or \|r\| > 15% (the build's own sanity bound) | flag |
| Q6 cross-source | \|CRSP − in-house\| > 5bp on a session | flag, both values listed |
| Q7 seams | the splice days 2024-12-31 / 2025-01-02 and 2026-07-20 / 07-21 | flag |

How flags are handled (revision 3; revision 2 allowed any "vendor defect" to
be fixed and Stage 0 re-run, with no criteria, at a stage that also computed
k from the P&L):

- **The headline is computed on the primary series as it stands at the end of
  Stage 0a.**
- **Only one kind of repair exists, and only in Stage 0a:** a stub print of the
  `BAD_PRINTS` type, the model being the ANGL 2013-08-02 repair in
  `build_etf_daily.py` (a closing print far outside the session's traded
  range, on thin volume, that fully reverses the next session). It is repaired
  only when **a third source**, independent of CRSP and of the in-house panel's
  vendors (for example the listing exchange's official close, or the issuer's
  published price history), confirms the true close. It enters `BAD_PRINTS`
  with a dated note naming that source. **No other flag alters a value.**
  Making DG1's build pass its own gates is DG1's work, not a repair.
- **Stage 0a ends with one commit** recording the SHA-256 of every input file
  the trials read (the staged ETF panel, the factor caches with their vintages,
  the DGS3MO cache, the frozen spec), the full Q1–Q7 flag list and any repair.
  Every later stage re-verifies those hashes before it reads an input, and a
  mismatch halts.
- **After Stage 0a nothing is repaired, dropped or substituted**: not a
  session, an instrument, a source or a factor. A defect found later is
  reported against the result, never fixed into it.
- **Robustness row R-Q** recomputes with flagged sessions excluded from the
  P&L statistics. It is reported and never chosen from.
- **Today's counts** (CRSP to 2024-12-31): one no-closing-trade day and one
  zero-volume day each for EMB and SPY; none for the other 17 (§2.1).

**Survivorship and selection, stated.** CRSP is free of survivorship bias, but
the slate's instruments are not: they are live funds named in 2026. The agenda
picked the most liquid fund per family from 2024 liquidity, on 2026-10-08. A
2008 investor could not have known that BKLN or CWB would grow and survive.

- **This bias cannot be measured from the repo.**
- **Its direction favours long-biased rules**, the TSH control and the D4
  factors. For long-short rules its direction is ambiguous.
- **It is mitigated, not removed,** by the leave-one-instrument-out rows (P11)
  and the holdout.

### 1.2 Returns, risk-free rate and execution (P3–P4)

**P3. Excess returns.**

- r^x = r − r_f, where r_f for session t is the last DGS3MO value published
  **strictly before** t, divided by 100 and by 252.
- Signals use excess returns wherever the paper does.
- **Every P&L is an excess return:** Σᵢ Hᵢ,ₜ₋₂ · r^x_i,t. Each sleeve is a
  self-financing overlay, as the papers' futures- and repo-financed returns
  are. The matrix passed to `evaluate()` is the excess-return matrix.
- `data/riskfree_daily.parquet` is not used: it has no fetcher and stops
  2026-07-16.

**P4. Execution (H1)** follows the harness's decide-t / fill-t+1 / earn-t+2
rule (shift(2)) through `evaluate()` in `scripts/cef/band_frontier.py`.

- `H.loc[t]` is decided after t's close, filled at t+1's close, and earns t+2.
- Monthly rules refresh at Eₘ, the last session of each calendar month in the
  primary panel's calendar.
- **A component timed by the calendar** (X2's month-end window, X3) may be
  decided early, because the trading calendar is published in advance. The
  information it uses is still data through t.
- **The run asserts the alignment (H7).** Any new helper, such as a month-end
  refresh or a block shuffle, is added to `band_frontier.py` visibly, with a
  test. **There is no new backtester.**

### 1.3 Sizing (P5, ruling 4)

**The spec values are pinned at approval (revision 3).** Revision 2 read the
vol target "at run time", so a spec change between approval and run would have
changed the trial without a note. Pinned:

| key, read through `scripts/cef/spec.py` | pinned value |
|---|---|
| `vol_target_annual` | **0.06** |
| `max_gross_stress` | **1.80** |
| SHA-256 of `ops/specs/cef_discount.frozen.json` | `c05035e55eaa89172f65d38a3485cb1c68123217177343b38576edf56583c02e` (git blob `3da1bd77271e28d3ccc11249fdf73530b176d3d1`) |

All three are as at main `9d7d317`, read 2026-10-13 [V: `spec.py`'s
`VOL_TARGET` and `MAX_GROSS_STRESS`; `git show 9d7d317:ops/specs/cef_discount.frozen.json | shasum -a 256`].

- **The run reads both values through `spec.py` and checks the file's
  SHA-256. Any mismatch halts at Stage 0a** and goes to the team lead.
- **If the spec changes before approval,** the approval names the hash it pins,
  and this table is amended in place with a dated note.

Every test is evaluated at three levels:

- **Raw sleeve:** the published rule at the paper's own scale (MOP's 40%/σ;
  HMM's w; H&S's notional 1; BSV's dollar ranks over σ).
- **Sized sleeve:** k × the raw sleeve, where **k = `vol_target_annual` /
  σ_fit**. σ_fit is the annualised (×√252) standard deviation of the raw
  sleeve's daily gross excess P&L over the fit P&L window (§1.6). k is
  computed at Stage 0b, after the trial is spent. It is one constant, derived
  on the fit window and applied unchanged to the holdout and live (H13).
  **The sized sleeve is never capped.**
- **Tradable sleeve:** the sized sleeve with the `max_gross_stress` cap applied
  row by row through `_cap_gross`, the sleeve's own operator. **Reported only.**

**The decision series is the sized, uncapped sleeve** (revision 3; revision 2
decided on the tradable sleeve).

- **Why.** k is a fit-window constant, so it uses data after each day it
  scales. For scale-free statistics that does not matter: Sharpe, t, DSR,
  alpha t, correlations, placebo ranks and the net Sharpes of the cost grid
  are the same for the sized sleeve as for the raw one, whatever k is. A cap
  breaks this. Whether it binds on a day depends on k, so it would carry
  future data into the decision statistics. X3 shows the case is real: P5 sets
  its window notional to about 0.06 / (σ_IEF·√(3/21)), which exceeds 1.80
  whenever IEF's annualised volatility is below 0.06 / (1.80·√(3/21)) ≈ 8.8%
  [arithmetic, taking X3's unconditional volatility as σ_IEF·√(3/21)]. Below
  that, the tradable X3 is capped on every window day.
- **Stages 1–3, 5, 7 and 8 are computed on the sized sleeve.** The review
  named stages 1–3 and 5. Stages 7 and 8 follow, so that one series decides
  throughout (§11 item 4).
- **D4's betas (stage 4) are measured on the sized sleeve**, as ruling 4
  requires. They are the one decision quantity that depends on k.
- **The tradable sleeve is a reported row** beside every stage, with the share
  of sessions on which the cap binds.
- **Scale-dependent statistics** (betas, alpha in %/yr, gross, turnover, cost
  drag) are reported at both the sized and the tradable scale.
- **One sizing rule for everything compared.** Every control, placebo and
  factor sleeve in a comparison (TSH, the BIL/SHY control, IEF on other days,
  the Treasury ladder, the long-only version) is sized by the same rule with
  its own k, and is uncapped.
- **Why k is a fit-window constant.** A time-varying ex-ante scalar would
  re-weight the published rule's returns through time, and would make it a
  different strategy from the paper's.

### 1.4 Costs, borrow and shorting (P6)

**Costs.**

- **Gross P&L is the headline.**
- Net is shown beside it at 5, 15 and 30bp per unit of one-way turnover
  (`band_frontier._stats`), with whether the sign flips across the grid.
  Turnover is Σ|ΔH|, as the harness defines it, of the sized sleeve (the
  decision) and of the tradable sleeve (reported).

**Borrow is UNMEASURED.** The repo holds no history of ETF borrow fees. Each
run reports the average short notional, so any rate can be applied. Every
distribution a short owes is inside CRSP `ret`.

**Shorting.**

- A name not shortable on the 2026-10-12 snapshot (MUB) is long-or-flat for the
  whole backtest. Shortable names are assumed shortable throughout; historical
  borrow availability is unknown, so this is a stated divergence.
- Live, the session re-reads `shortable` at send and skips a short that has
  flipped.

### 1.5 Windows and the holdout (P7)

**Fit window.** From each test's first decision under its declared breadth rule
(§2.2) to 2022-12-30. Under H1 its P&L runs from the first decision + 2
sessions to 2022-12-30 (§1.6). Nothing is fitted: "fit" means the in-sample
evaluation window. Eras follow H5 (2005–09, 2010–14, 2015–19, 2020–22,
2023–26).

**Holdout.** 2023-01-03 to **2026-09-30, for all five tests** (revision 3):
939 sessions, 3.73 years [V: `slate_feasibility.py`, 2026-10-13]. Revision 2
ended it at "the primary panel's last date at run time", which let the run
date set its length.

- **No holdout opens until all five fit verdicts are committed** (revision 3;
  revision 2 opened each test's holdout after its own verdict). A test left
  UNRUN at Stage 0a is committed as UNRUN, and that counts as its verdict
  (§11 item 5).
- **Then each test's holdout is opened once**, whatever its fit verdict, so
  the record is complete.
- **Every fit-derived quantity is frozen:** k, the rules, and every threshold
  computed from the fit.
- **The holdout P&L comes from the continuous series.** Until the holdout
  opens, every computation is truncated by `fit_only`. When it opens, each
  sleeve is evaluated once, through `evaluate()`, from its first decision to
  2026-09-30, and the holdout rows are sliced from that one P&L. So the
  positions decided on 2022-12-29 and 2022-12-30 earn the first two holdout
  sessions, as they would have live; the holdout never restarts flat. The
  fit rows of that series must equal the fit stages' P&L exactly (asserted).

**Holdout rule (declared now).**

- **Statistic:** the mean daily excess P&L of the sized sleeve.
- **Pass:** for a fit PASS-candidate, the holdout mean has the same sign as the
  fit mean. Otherwise KILL (D3).
- **Reported beside it:** the holdout Sharpe, its HAC t, a stationary-bootstrap
  95% CI, and the probability of the observed sign under the fit Sharpe.
- **False-kill rate:** at a true Sharpe of 0.5 the sign rule fires by chance
  with probability Φ(−0.5·√3.73) = 0.167 [V: `slate_feasibility.py`,
  2026-10-13].
- **The holdout can kill; it can never rescue a failed fit.**

### 1.6 Inference (P8)

| quantity | method, declared |
|---|---|
| **headline** | annualised Sharpe (mean × 252 / sd × √252) of the sized sleeve's daily gross excess P&L over the **fit P&L window: from the first decision + 2 sessions (H1) to 2022-12-30**. Every statistic of every stage, and the T passed to `_dsr`, use that window (or the narrower one a row names). **Never `evaluate()['gross_sr']`**, which averages over the flat sessions before the first decision too; the statistics are computed on the sliced daily series (revision 3) |
| **HAC t of the mean** | Newey–West (Bartlett) with **L = 21 sessions**, through `scripts/cef/w4_artifacts.py::nw_t(x, lags=21)`. L is one rebalance month, and is fixed above the Newey–West (1994) rule ⌊4(T/100)^(2/9)⌋, which gives 8–9 at these fit lengths and is printed as a sensitivity |
| **bootstrap CIs** | stationary bootstrap (Politis–Romano) with **expected block 21 sessions**, 10,000 resamples, seed 20261012: 95% percentile CIs for the mean (%/yr) and the Sharpe. A mean block of 63 sessions, and the repo's moving-block bootstrap (`w4_artifacts.block_boot_t`), are printed as second methods |
| **the bar (decision)** | `scripts/cef/validate.py::_dsr(obs, T, sk, ku, 5)` on the fit-window gross series, with **sk = `pd.Series.skew()` and ku = `pd.Series.kurt() + 3`** of the same daily series, as `scripts/cef/validate.py:342` computes them (pandas' `kurt` is excess kurtosis; `_dsr` takes raw kurtosis); **PASS > 0.95** (ruling 2) |
| beside it, labelled, never deciding | SR·√years against √(2 ln 5) = 1.794 (the agenda's reading); `_dsr` at N = 162 (LEGACY) |
| **power** (stated now, §2.2) | the Sharpe each test must show, the Sharpe at 80% power, and P(pass) **at the draft's own expected Sharpes**, with the SE taken from `_dsr`'s own denominator. The published Sharpe, and 0.42 × it (McLean & Pontiff's 58% post-publication fall), are printed as upper references only (revision 3) |
| monthly regressions | the same HAC estimator with L = ⌊4(T_m/100)^(2/9)⌋ = 4 at these fit lengths |

### 1.7 Regressions (P9)

All regressions are OLS with statsmodels HAC covariance (maxlags 21 daily, 4
monthly), as W4 does. Alpha is reported in %/yr (× 252 daily, × 12 monthly)
with its t. Every factor is an excess return built from the primary panel and
P3's r_f:

- **MKT** = SPY − r_f
- **TERM** = IEF − r_f
- **HY** = HYG − IEF
- **IG** = LQD − IEF
- **COMMOD** = DBC − r_f
- **GOLD** = GLD − r_f
- **INTL** = EFA − SPY (revision 3; revision 2 had EFA − r_f)
- **EM** = EEM − SPY (revision 3; revision 2 had EEM − r_f)

**Collinearity, declared before any regression runs (revision 3).** As
revision 2 wrote them, INTL and EM were largely MKT again, so their betas would
have been unstable and a \|β\| rule on them close to arbitrary.

- **INTL and EM are spreads over SPY**, so they carry the non-US part of those
  markets. HY and IG were already spreads over IEF.
- **The \|β\| ≤ 0.10 rule applies to the OLS point estimates**, not to a
  confidence bound.
- **Every R-D4 prints each factor's VIF and its HAC 95% CI** beside the point
  estimate.
- **No factor is re-specified, orthogonalised or dropped after a result is
  seen.** A test that fails D4 on a factor stays failed.
- **A TERM-hedged X3 is a new trial**, not a repair of X3 (§6).

| regression | role | specification |
|---|---|---|
| **R-D4** | **decision (ruling 4)** | daily **sized** sleeve on its declared D4 set (each test's section), over the fit P&L window ∩ the factors' history. **Pass: alpha t ≥ 3.0 and every \|β\| ≤ 0.10** (OLS point estimates). Where HYG's history (from 2007-04-12) would shorten the fit, two R-D4 regressions are declared and **both must pass**: the full fit without HY and IG, and the window from 2007-04-12 with them. The shorter one binds the power (§2.2) |
| **R-FF** | reported | R-D4's set plus French MKT-RF, SMB, HML and UMD (daily; French's library, the vintage recorded) |
| **R-AQR** | reported, monthly | the sleeve's monthly excess P&L on the AQR factors named in each section (TSMOM, TSMOM^FI / ^EQ / ^CM, VME MOM, MOMLS_VME_FI) |
| **R-LONG** | reported (X1, X4) | the sleeve on its own long-only version (sign ≡ +1, sized by P5): MOP's own check, p.236 |
| **R-SPAN** | **decision (X5 only)** | X5's sized sleeve on X1's sized sleeve plus MKT, TERM, HY, IG. **Pass: alpha t ≥ 1.96**; otherwise X5 is spanned by trend (BSV p.23) |

### 1.8 Controls and placebos (P10)

- **Named control, per test.** Its kill rule is in the test's decision table.
  A control is sized by P5 and run through the same harness.
- **Block-shuffled-signal placebo.** The rows of the sized `H` are permuted
  in contiguous 21-session blocks while returns stay fixed. That keeps each
  position's size and turnover and destroys its timing. 1,000 draws, seed
  20261012. **KILL (D1) if the real gross Sharpe ≤ the placebo's 95th
  percentile.**
- **shift(3), the stale-price check.** `evaluate(H.shift(1), R)`.
  - **X1, X4, X5:** monthly signals should barely change, so KILL if the
    shift(3) Sharpe < ½ × the shift(2) Sharpe.
  - **X2, X3:** reported only. Their papers show the effect is short-lived by
    mechanism: HMM Fig. 4, pressure that peaks by day 2–4 and reverts within
    about 15 sessions; H&S Table 5, the last day carries the largest return.
    A one-day delay is expected to cost them, and that cost is not staleness.

### 1.9 Robustness: reported, never chosen from, and none of it can rescue a failed headline (P11)

- Era rows (H5), with turnover sd/mean.
- The share of calendar years with positive gross P&L, and the first half of
  the fit against the second.
- Leave-one-instrument-out for X1, X4 and X5: min, median and max Sharpe.
- The 5/15/30bp cost grid with turnover.
- **Capacity:** the sleeve capital at which the largest single-name trade on a
  median rebalance day reaches 1% of that name's 63-session median dollar
  volume. Participation is also shown at $1m, $10m and $100m of sleeve capital.
- Month-end refresh offsets for X1, X4 and X5 (`calendar_offset`, all 21
  offsets) as an error band.
- Bootstrap mean block 63.
- The Newey–West (1994) automatic lag.
- The tradable (capped) sleeve against the sized one, with the share of
  sessions on which the cap binds.
- Row R-Q (flagged sessions excluded).
- **The in-house panel in place of CRSP**, for source sensitivity.

### 1.10 Correlation with the CEF book (P12, ruling 3: reported only)

- **The book's series:** daily gross total-return P&L, built as
  `scripts/xasset/book_profile.py` builds it (v7 band, gross-capped), from the
  book's first position. **The X side is each sized sleeve**; correlations are
  scale-free, so the raw sleeve gives the same values.
- **What is reported:**
  - daily ρ;
  - non-overlapping 21-session ρ, Pearson and Spearman;
  - 21-session ρ in HY-stress windows (the worst quintile of 21-session
    HY_XS), as `diversification_screen.py` builds them.
- **Rows:** fit and holdout. The CEF price panel ends 2026-09-28 [V, orient],
  so the holdout row stops there.
- **Never a kill.** The values feed only the Σ⁻¹·IR sizing of plan §4.

### 1.11 The order of evaluation (P13): the same for every test

Revision 3 splits revision 2's Stage 0, which computed k (and so read the
raw sleeve's whole fit-window P&L) while spending no trial, and allowed repairs
with no criteria.

| stage | statistic | rule | outcome if the rule fails |
|---|---|---|---|
| **0a** | DG1–DG3; the spec pin (§1.3); the P2 screen Q1–Q7; any repair, of the one permitted kind (§1.1). **No return is combined into a P&L.** Ends with one commit of the input files' SHA-256s, the flag list and any repair | every gate clears; Q1 clean; the spec pin matches | **no trial spent.** A gate that cannot clear leaves each test that needs it **UNRUN**, and N stays 5. Referred to the team lead |
| — | **the trial is spent from here.** XASSET's trials-used k−1 → k, in a commit made before this test's Stage 0b computes anything | — | — |
| **0b** | the input hashes re-verified; then k, turnover, gross and the cap-binding share | a hash mismatch halts | the trial is spent; referred to the team lead |
| 1 | headline: sized gross Sharpe, NW t (L = 21) | t ≥ 1.96 | **KILL D1**: no detectable edge |
| 2 | named control (section) | section's rule | **KILL** (code in section) |
| 3 | placebo; shift(3) where it decides | §1.8 | **KILL D1** |
| 4 | R-D4 on the sized sleeve (and R-SPAN for X5) | §1.7 | **KILL D4** (or "spanned", X5) |
| 5 | the bar: `_dsr` at N = 5 | > 0.95 | **NEITHER**: real at most, but below the bar. No sleeve and no re-test on these data. The team lead rules WATCH or D5 |
| 6 | the fit verdict is committed | — | — |
| 7 | holdout sign (§1.5), opened only once **all five** fit verdicts are committed | same as fit | **KILL D3** |
| 8 | a PASS's net Sharpe at 15bp (sized sleeve) | > 0 | labelled **D2**: no real-money sleeve. Paper only by team-lead ruling |

**After Stage 0a nothing is repaired, dropped or substituted.** **Every
statistic of every stage is computed and reported, whatever the verdict,** on
the sized sleeve with the tradable sleeve's value beside it. The verdict is the
first failing rule in this order. A PASS needs stages 1–5 and 7.

### 1.12 Scripts and holdouts of names (P14)

- **Scripts:** one per test, `scripts/xasset/x<k>_<name>.py`. Each imports
  `evaluate`, `_stats`, `fit_only` and `calendar_offset` from
  `scripts/cef/band_frontier.py`, `_dsr` from `scripts/cef/validate.py`, and
  `nw_t` from `scripts/cef/w4_artifacts.py`.
- **Order:** X5 runs after X1, because R-SPAN needs X1's series. X2's
  reported week4-on-X3 regression (§5) needs X3's series, so it is reported
  once both have run; it decides nothing.
- **The 27-name holdout:** no X instrument is in `data/cef/cef_universe.csv`
  (checked 2026-10-12), so no X-test consumes it.

---

## 2. Feasibility, measured today (zero trials)

### 2.1 Instruments

**Source:** `python3 scripts/xasset/slate_feasibility.py --alpaca --crsp --factors`
→ `results/xasset/feasibility/slate_feasibility_2026-10-12.csv`.

- **CRSP** counts come from `dsf` through the R2 mirror.
- **Alpaca flags** were read on the cef paper key at 2026-10-12T22:42:40–41Z.
  They **are true on that date only** (landmine 5) [V].
- **CRSP's first row is each fund's single NULL-`ret` day**; its first return
  is the next session.

| symbol | used in | CRSP PERMNO | CRSP rows (first → last) | CRSP no-close-trade / zero-vol days | in-house first return → last; gaps | exchange | shortable / easy to borrow |
|---|---|---:|---|---|---|---|---|
| HYG | X1 X4 X5; D4 HY | 91933 | 2007-04-11 → 2024-12-31 | 0 / 0 | 2007-04-12 → 2026-10-09; 0 | ARCA | yes / yes |
| LQD | X1 X4 X5; D4 IG | 89467 | 2002-07-26 → 2024-12-31 | 0 / 0 | 2002-07-31 → 2026-10-09; 0 | ARCA | yes / yes |
| IEF | X1–X5; X3 control; X5 ladder; D4 TERM | 89469 | 2002-07-26 → 2024-12-31 | 0 / 0 | 2002-07-31 → 2026-10-09; 0 | NASDAQ | yes / yes |
| TLT | X1 X4 X5; X5 ladder | 89468 | 2002-07-26 → 2024-12-31 | 0 / 0 | 2002-07-31 → 2026-10-09; 0 | NASDAQ | yes / yes |
| EMB | X1 X4 X5 | 92491 | 2007-12-19 → 2024-12-31 | **1 / 1** | 2007-12-20 → 2026-10-09; 0 | NASDAQ | yes / yes |
| PFF | X1 X4 X5 | 91874 | 2007-03-30 → 2024-12-31 | 0 / 0 | 2007-04-02 → 2026-10-09; 0 | NASDAQ | yes / yes |
| MUB | X1 X4 | 92273 | 2007-09-10 → 2024-12-31 | 0 / 0 | 2007-09-11 → 2026-10-09; 0 | ARCA | **no / no** |
| BKLN | X1 X4 X5 | 12631 | 2011-03-03 → 2024-12-31 | 0 / 0 | 2011-03-04 → 2026-10-09; 0 | ARCA | yes / yes |
| CWB | X1 X4 X5 | 92914 | 2009-04-16 → 2024-12-31 | 0 / 0 | 2009-04-17 → 2026-10-09; 0 | ARCA | yes / yes |
| SPY | X2 X4; D4 MKT | 84398 | 1993-01-29 → 2024-12-31 | **1 / 1** | 1993-02-01 → 2026-10-09; 0 | ARCA | yes / yes |
| EFA | X4; D4 INTL | 89129 | 2001-08-17 → 2024-12-31 | 0 / 0 | 2001-08-28 → 2026-10-09; 0 | ARCA | yes / yes |
| EEM | X4; D4 EM | 89730 | 2003-04-11 → 2024-12-31 | 0 / 0 | 2003-04-15 → 2026-10-09; 0 | ARCA | yes / yes |
| GLD | X4; D4 GOLD | 90448 | 2004-11-18 → 2024-12-31 | 0 / 0 | 2004-11-19 → 2026-10-09; 0 | ARCA | yes / yes |
| DBC | X4; D4 COMMOD | 91129 | 2006-02-03 → 2024-12-31 | 0 / 0 | 2006-02-07 → 2026-10-09; 0 | ARCA | yes / yes |
| SHY | X2 control; X5 ladder | 89470 | 2002-07-26 → 2024-12-31 | 0 / 0 | 2002-07-31 → 2026-10-09; 0 | NASDAQ | yes / yes |
| BIL | X2 control | 92027 | 2007-05-30 → 2024-12-31 | 0 / 0 | 2007-05-31 → 2026-10-09; 0 | ARCA | yes / yes |
| IEI | X5 ladder | 91705 | 2007-01-11 → 2024-12-31 | 0 / 0 | 2007-01-12 → 2026-10-09; 0 | NASDAQ | yes / yes |
| TLH | X5 ladder | 91704 | 2007-01-11 → 2024-12-31 | 0 / 0 | 2007-01-12 → 2026-10-09; 0 | ARCA | yes / yes |
| AGG | reference only | 89848 | 2003-09-26 → 2024-12-31 | 0 / 0 | 2003-09-30 → 2026-10-09; 0 | ARCA | yes / yes |

**What the table establishes.**

- **CRSP PERMNOs agree with the build.** For the ten slate names already in
  `build_etf_daily.py` (which holds 13 tickers; ANGL, FALN and JNK are not
  slate names), the PERMNOs CRSP resolves and their row counts equal
  the build's `PERMNOS` map.
- **The in-house panel starts up to six sessions after CRSP** (EFA). The cause
  was not investigated, and it does not matter here: P1 makes CRSP primary.
- **The breadth rules give the same first decisions under either source.**
  The names that bind (HYG and PFF for X1, GLD for X4, PFF for X5) have the
  same first return in CRSP as in-house. IEF's CRSP start two sessions earlier
  (first return 2002-07-29) does not move X2's or X3's first month-end
  (2002-08-30).

**Factor files, reachable today (coverage only; DG2 writes the fetcher):**

| file | columns | coverage |
|---|---|---|
| AQR TSMOM | TSMOM, TSMOM^CM, ^EQ, ^FI, ^FX | 1985-01-31 → 2026-05-29 |
| AQR VME | VAL, MOM, …, MOMLS_VME_FI, MOMLS_VME_EQ, … | 1972-01-31 → 2026-07-31 |
| French FF5 + UMD | MKT-RF, SMB, HML, RMW, CMA, UMD | daily to 2026-08-31, vintage 202608 (REFERENCES §8, 2026-10-11) |

### 2.2 Fit windows, the bar, and power (restated in revision 3)

**Source:** `python3 scripts/xasset/slate_feasibility.py`, the per-test block,
re-run 2026-10-13 [V]. Arithmetic on the bar, on the calendar and on the
draft's own expectations; no return is read.

**What changed from revision 2, and why** (the review's fix 8):

- **T is the P&L session count**, from the first decision + 2 sessions (H1)
  to 2022-12-30: the T the trial will pass to `_dsr`. Revision 2 counted from
  the first decision + 1.
- **The SE is `_dsr`'s own.** Power is P(observed Sharpe > required Sharpe),
  with the observed Sharpe normal around the true one and its SE taken from
  `_dsr`'s denominator at skew 0 and kurtosis 3 (`sr_se`). Revision 2 used
  1/√years. Two tests in `scripts/xasset/tests/test_slate_feasibility.py` hold
  this: `sr_se` equals the SE implied by `_dsr`'s z, and a simulation that
  draws daily returns at a known Sharpe and applies `_dsr` to each path agrees
  with the closed form.
- **Power is stated at the draft's own expected Sharpes** (each test's
  "Expectation" [U]; the mid is the midpoint). X3's section gives no number, so
  its bracket runs from 0.42 × the published Sharpe to the published Sharpe.
- **The published Sharpes are upper references, not expectations.** Revision
  2's headline power for X2 (0.94) was at HMM's in-sample 1.11 on futures,
  with signals used one session earlier than shift(2) allows.
- **The D4 column uses the binding regression.** Where two R-D4 regressions are
  declared (X2, X3, X4), the one from HYG's first return is shorter and binds:
  it needs IR 0.76, not revision 2's 0.67 (X2, X3) or 0.73 (X4).

**Table A. The bar, and power at the draft's own expectations.**

| test | breadth rule | first decision | first P&L | T, sessions (yr) | **required SR** (N = 5) | SR for 80% power | the draft's expected SR [U] | **P(pass)** at expected low / mid / high |
|---|---|---|---|---|---:|---:|---|---|
| X1 | ≥ 5 of 9 with 12 months | 2008-04-30 | 2008-05-02 | 3,693 (14.65) | 0.90 | 1.12 | 0.30–0.60 (§4) | 0.011 / 0.043 / 0.127 |
| X2 | both, 1 month | 2002-08-30 | 2002-09-04 | 5,118 (20.31) | 0.76 | 0.95 | 0.20–0.80 (§5) | **0.006 / 0.118 / 0.566** |
| X3 | IEF, 1 month | 2002-08-30 | 2002-09-04 | 5,118 (20.31) | 0.76 | 0.95 | none stated (§6); bracket 0.37–0.88 | 0.038 / 0.267 / 0.700 |
| X4 | ≥ 7 of 14 with 12 months | 2005-11-30 | 2005-12-02 | 4,299 (17.06) | 0.83 | 1.04 | 0.40–0.80 (§7) | 0.037 / 0.168 / 0.446 |
| X5 | ≥ 4 of 8 with 36 months | 2010-03-31 | 2010-04-05 | 3,210 (12.74) | 0.96 | 1.20 | 0.00–0.40 (§8) | < 0.001 / 0.003 / 0.022 |

**Table B. Published Sharpes: upper references only, never an expectation.**

| test | published SR (source) | why it is an upper bound here | P(pass) at published | at 0.42 × published | agenda reading: SR·√yr = 1.794 needs SR ≥ (labelled, never deciding) |
|---|---|---|---:|---:|---:|
| X1 | 0.49 (BSV Table IV-A, bond trend) | 10-year government bond indices, not credit ETFs | 0.059 | 0.004 | 0.47 |
| X2 | 1.11 (HMM Table 6) | in-sample; futures; signals used one session earlier than shift(2) allows, so day 1 is kept | 0.941 | 0.090 | 0.40 |
| X3 | 0.88 (H&S Table 3) | a 10-year zero, inside the paper's own sample; t = 3 carries the paper's own selection from its 1–10 sweep | 0.700 | 0.038 | 0.40 |
| X4 | 0.98 (BSV Table IV-A, multi-asset trend) | an equal-volatility composite over many markets, FX included | 0.728 | 0.041 | 0.43 |
| X5 | 0.31 (BSV Table IV-A, bond momentum) | 10-year government bond indices | 0.010 | 0.001 | 0.50 |

**Table C. D4: the alpha leg on the binding window.** These treat the whole
sleeve Sharpe as alpha (all betas zero), so they are upper bounds on P(D4 pass)
even before the β leg.

| test | R-D4 regressions | binding window, T (yr) | alpha t ≥ 3 needs IR ≥ | P(alpha t ≥ 3) at expected low / mid / high | at published |
|---|---|---|---:|---|---:|
| X1 | one (HYG trades from the first decision) | 2008-05-02 → 2022-12-30, 3,693 (14.65) | 0.78 | 0.032 / 0.101 / 0.241 | 0.131 |
| X2 | two; the post-2007 one binds | 2007-04-12 → 2022-12-30, 3,960 (15.71) | **0.76** | 0.014 / 0.154 / 0.568 | 0.919 |
| X3 | two; the post-2007 one binds | 2007-04-12 → 2022-12-30, 3,960 (15.71) | **0.76** | 0.063 / 0.301 / 0.687 | 0.687 |
| X4 | two; the post-2007 one binds | 2007-04-12 → 2022-12-30, 3,960 (15.71) | **0.76** | 0.079 / 0.267 / 0.568 | 0.812 |
| X5 | one | 2010-04-05 → 2022-12-30, 3,210 (12.74) | 0.84 | 0.001 / 0.011 / 0.058 | 0.029 |

**The β leg, which no power figure above includes** [arithmetic; the factor
volatility is U]:

- On a sleeve sized to 6%/yr, a lone factor j's beta is ρⱼ·0.06/σⱼ. So
  \|β\| ≤ 0.10 needs \|ρⱼ\| ≤ 0.10·σⱼ/0.06.
- Against TERM, at an IEF volatility of about 6.5%/yr [U], that is
  **\|ρ\| ≲ 0.11**. A sleeve whose daily P&L correlates with IEF by more than
  about 0.11 fails D4 whatever its alpha.
- The bound is tightest for the least volatile factor, which may be a spread
  (HY or IG) rather than TERM.
- **No factor volatility is measured before Stage 0b.** For X3, IEF's
  volatility on the fit window is, near enough, X3's σ_fit, a Stage 0b
  quantity.

**What a null result means, stated before anything runs** (restated in
revision 3; the team lead asked for this so that a null can be read):

- **At the draft's own expected Sharpes, no test is well powered.** At the
  midpoints P(pass) is 0.043 (X1), 0.118 (X2), 0.267 (X3), 0.168 (X4) and
  0.003 (X5). Only the top of X2's range (0.566) and the top of X3's bracket
  (0.700, which is the published figure) pass more often than not.
- **X1 and X5 are underpowered even at the top of their ranges** (0.127 and
  0.022).
- **D4 can only lower these.** A PASS needs the bar and D4 together, so
  P(PASS) is at most the smaller of Table A's and Table C's figures (Table A's
  at every midpoint), and the β leg is in neither.
- **So a pass is informative for all five, and a fail, on its own, for none.**
  A fail of X2, X3 or X4 is evidence only against Sharpes near the 80%-power
  level (0.95, 0.95 and 1.04), which lie above every expected Sharpe in this
  note. It does not show that the mechanism is absent. Revision 2's "a fail is
  informative only for X2, X3 and X4" is withdrawn.

### 2.3 Blockers found, and what clears each

| blocker | blocks | clears it |
|---|---|---|
| 9 of the 19 names are not yet in `data/etf_daily.parquet` | P1's CRSP-primary source | **DG1** |
| AQR factors have no fetcher | R-AQR | **DG2** |
| `data/riskfree_daily.parquet` has no fetcher and stops 2026-07-16 | P3 | **DG3** (DGS3MO through the existing FRED fetcher; fetched 2026-10-12, 1981-09-01 → 2026-10-08 [V]) |
| **No X instrument is NYSE-listed**; `ASSET_EXCHANGE_SIP_NAME` maps NYSE only | the auction-print P&L line for any X sleeve on paper | plan item 0.2. **Blocks phase 3, not the trials** |
| The third, distribution-adjusted P&L line is merged but not released (`02a2fda`) | scoring yield-carrying X sleeves on paper | plan item 0.4. **Blocks phase 3, not the trials** |
| MUB is not shortable | MUB shorts | P6: long-or-flat; X5 excludes MUB by declaration |
| `data/futures_daily.parquet` holds only rates futures to 2025-04-25, and has no fetcher | a longer, futures-based fit | **checked and not used** |
| Credit ETF history starts 2007–2011 | X1 and X5 power | nothing in the repo; stated in §2.2 |

---

## 3. Graveyard check (`/graveyard`, `docs/RESEARCH_STATE.md`)

| test | nearest dead mechanism | how it differs | stale-price well? |
|---|---|---|---|
| X1 | **`credit_rv`** (cross-sectional RV on credit ETFs; D1). **`S3-wrapper`** (a credit-quality premium in costume; D4). **Duration timing** (agenda, closed) | A time-series signal on each ETF's **own 12-month** return. The D4 danger, that trend is just long credit and duration in a bond bull market, is exactly what stages 2 (TSH) and 4 (R-D4) test. Forward-rate duration timing is closed; trend is a separate family with the longest out-of-sample record (agenda A1) | **No**: executable close-to-close returns; stage 3 shift(3) checks it |
| X2 | **`raw-flow-z`** (D1). **`short-pressure`** (the rates control scored higher). **`leadlag`** (non-synchronous prices) | The flow is **mechanical**, signed by mandate and computed from public returns, with no flow data. The rates control that killed `short-pressure` is built in ({BIL: +w, SHY: −w}, duration-signed as X2's IEF leg since revision 3). SPY and IEF close synchronously, though shift(2) loses the paper's day 1 | **No** |
| X3 | **Treasury auction cycle** (agenda, closed: D2) | A month-end index-rebalancing flow at 2 trades a month, not the auction cycle. **It shares that trade's cost problem** (§6) | **No** |
| X4 | X1's, plus **"Daily equity → credit"** (closed; `leadlag`) | Monthly, on each asset's own past | **No** |
| X5 | **`credit_rv`** (D1). **Bond-level momentum** (closed: 0.00%/month without winsorization). **Duration timing** (closed) | 12-1 continuation. **But BSV find that trend subsumes it** (p.23), which is why R-SPAN decides. On ETFs of mixed duration a raw-return rank collapses into duration timing, which is why the Treasury ladder is its control | **No**, but it sits nearest the graveyard |

---

## 4. X1 — credit and rates trend

**Mechanism and the other side.**

- **The mechanism.** Prices under-react to news, then over-react with a delay.
  Speculators "earn positive excess returns at the expense of hedgers, who may
  be willing to compensate speculators for liquidity provision in order to
  maintain their hedge" (MOP p.249).
- **The losers here** are holders who must keep duration and spread exposure
  for liability or benchmark reasons. They persist because the hedge is the
  mandate, not a view.
- **Why the ETF's AP mechanism does not arbitrage it away:** APs pin an ETF to
  its basket, while this signal is the basket's own trend. Trend is crowded,
  and its record has been "mixed since 2008" (HOP, §12b).

**Instruments.** The agenda's nine, declared on 2026-10-08 before any return
was computed. MUB is long-or-flat (P6).

**Published parameters, verbatim, and how they map.**

| parameter | published | source | applied here |
|---|---|---|---|
| signal | sign of the past 12-month excess return; k = 12, h = 1 | MOP §4, p.236; Fig. 2 caption, p.237 | compounded daily excess return over (E₍ₘ₋₁₂₎, Eₘ]; long if ≥ 0, short if < 0 (HLWZ's tie rule, Table 10 caption, p.791) |
| ex-ante volatility | σ²ₜ = 261 Σ (1−δ)δⁱ (r₍ₜ₋₁₋ᵢ₎ − r̄ₜ)²; centre of mass δ/(1−δ) = 60 days; σ at t−1 applied to t | MOP §2.4, eq. 1, p.233 | `ewm(com=60, adjust=True)` mean and variance of daily excess returns through Eₘ, × 261 |
| position | 40%/σₜ₋₁ | MOP §4.1, eq. 5, p.236 | **raw sleeve verbatim**; P5 then scales it to the vol target |
| portfolio | equal-weighted over the Sₜ securities available | MOP §4.1, p.236 | 1/Sₜ over eligible names |
| holding | one month | MOP §4, p.236 | refreshed at each Eₘ under H1; one session behind MOP |
| sample start | from 1985 "to ensure that a comprehensive set of instruments have data" | MOP p.236 | the first Eₘ with ≥ ⌈9/2⌉ = 5 names holding 12 months of returns: **2008-04-30** |

**Windows.** Fit from the first decision (2008-04-30) to 2022-12-30, 14.7
years. Five names are eligible in 2008 (LQD, IEF, TLT, HYG, PFF); all nine from
2012-03. Holdout per §1.5.

**D4 set.** MKT, TERM, HY, IG, one regression, because HYG exists from the
first decision.

**Reported regressions.**

- **R-FF.**
- **R-AQR** on TSMOM^FI and TSMOM. This shows whether the ETF version adds
  anything beyond the published factor.
- **R-LONG.**

**Decision table.**

| stage | statistic | rule | if it fails |
|---|---|---|---|
| 1 | sized gross Sharpe; NW t | t ≥ 1.96 | KILL D1 |
| 2 | **TSH control** (HLWZ eq. 17, p.788): the same weights, with the sign of the **inception-to-date** cumulative excess return; volatility weighting as in Table 10 Panel B, p.791; sized by P5 | X1's Sharpe exceeds TSH's **gross and at each of 5, 15 and 30bp** (TSH charged its own turnover). Reported beside it: the NW t of the daily P&L difference, and a bootstrap CI for the Sharpe difference | KILL D4: the historical-mean rule. H2's turnover matching cannot be met without altering one of the two published rules, so this stricter dominance test replaces it |
| 3 | placebo; shift(3) | §1.8 | KILL D1 |
| 4 | R-D4 | alpha t ≥ 3.0, \|β\| ≤ 0.10 | KILL D4 |
| 5 | `_dsr`, N = 5 | > 0.95 | NEITHER |
| 7 | holdout sign | as fit | KILL D3 |
| 8 | net at 15bp | > 0 | D2 label |

**Turnover and costs.**

- **The nearest measured relative** is a 10-ETF 12-month sign rule with 63-day
  volatility: 11.1 turns a year at a mean gross of 3.3×, 2008–2022
  (`scripts/xasset/trend_turnover.py`, 2026-10-08) **[S: not re-run; re-running
  it is outside a zero-trial gate]**.
- **X1's turnover scales with its gross under P5.** Its own figure is printed
  at Stage 0b.

**Expectation** [U]: a gross Sharpe of 0.3–0.6, from bond trend; no
credit-trend figure was found. P(pass) across that range is 0.011 / 0.043 /
0.127 (§2.2), so the likeliest outcome is NEITHER, or a kill by TSH.

**Reverse once trading (H11).**

- **Fidelity at each month-end:** the live target must equal the trial
  script's target on the same panel, to whole-share rounding. Any other
  difference halts the sleeve as a bug.
- **Reversal at 24 refreshes:** reverse if the live cumulative gross return is
  below the 5th percentile of the trial's own 24-month returns. That
  percentile is re-measured on the read date by a stationary bootstrap with
  mean block 21.
- **At any time:** reverse if the live drawdown exceeds the fit's worst,
  re-measured. **No threshold is written here as a number (H14).**

**Divergences from the backtest.**

- Paper executes `late_market` day orders, not MOC (CLAUDE.md rule 3).
- Whole shares only.
- No auction-print line until plan item 0.2 is done.
- No dividends on paper until the third P&L line is released.
- Shorts are re-read daily.
- The account's gross cap is shared with the CEF book. The decision series is
  uncapped, and the reported tradable row caps the sleeve alone.
- Borrow is unmodelled.

---

## 5. X2 — front-running pension and balanced-fund rebalancing

**Mechanism and the other side.**

- **The losers.** Pensions, balanced funds and target-date funds rebalance a
  stock–bond mix by calendar or by drift band, "as stipulated by their
  investment policies" (HMM pp.6–8). They favour month-end, both to pay
  benefits and to track benchmarks that rebalance monthly (pp.7–8). The paper
  puts the cost to them at "about $16 billion annually" (abstract, p.3).
- **Why they persist:** the policy, not the price, sets the trade.
- **Why it is not arbitraged away.** Front-runners exist ("hedge funds do
  deploy front-running strategies", p.41), but the trade is risky in timing and
  size (p.39). Its profits concentrate where liquidity providers are
  constrained: 17.96%/yr against 3.79%/yr by liquidity risk (Table 6 Panel C,
  p.38).
- **No AP mechanism is involved.**

**Instruments.** SPY and IEF ("iShares 7-10 Year Treasury Bond ETF", Alpaca
asset name).

**Published parameters, verbatim, and how they map.**

| parameter | published | source | applied here |
|---|---|---|---|
| simulated portfolio | 60% S&P 500 / 40% 10-year note; wₜ₊₁ = wₜ(1+R^SP)/[wₜ(1+R^SP) + (1−wₜ)(1+R^10Y)] | pp.2, 10; App. B, p.53 | SPY and IEF total returns, in place of the paper's E-mini and 10-year note futures (App. A, p.52) |
| Threshold signal | rebalance to 60% when the weight is more than δ from target; signal = drifted weight − 60% (B.1); **averaged over δ = 0%, 0.1%, …, 2.5%** | eq. 2, p.12; p.53 | 26 portfolios. The state is the post-trade weight at each close; the signal is the pre-trade drift. **Each starts at 60% at the close of 2002-07-29**, IEF's first CRSP return (revision 3) [V: `data/etf_daily.parquet`, IEF's first row, source `crsp`, read 2026-10-13; SPY's CRSP returns start 1993-02-01]. The Calendar portfolio is reset to 60% at every Eₘ, so its start matters only until 2002-07-31 |
| Calendar signal | rebalance on the last business day of each month (B.2) | p.9; p.53 | as published |
| week4 | the last 5 days of the month | p.14 | the month's last 5 sessions |
| strategy | R = (R^SP − R^10y)·w; w = average of −Threshold/1.5% and a modified Calendar: **sign(−Calendar) in week4, sign(Calendar₋₄) on the new month's first business day, 0 otherwise** | §4, pp.37–38 | raw sleeve H = {SPY: +w, IEF: −w}; P5 then sizes it |

**The one declared reading of "Calendar₋₄", and why.** The paper defines it no
further. It is read here as **the Calendar signal at the close four sessions
before the day it is set**, which is the 4th-to-last session of the old month
(the second session of week4). Three reasons:

1. **It follows the paper's notation.** Signals are indexed by session, so a
   subscript −4 is a lag.
2. **It is the quantity the reversal concerns.** That session lies inside
   week4 and before the month-end rebalance resets the Calendar signal to zero.
   It therefore carries the overweight that the rebalancers traded, and Fig. 4
   (pp.21–22) shows that pressure reversing.
3. **The other readings land within a session of it** inside the same window.

**The other readings are not run.** Running them would be a sweep.

**Mapping under H1.** The paper's wₛ uses signals through s and earns s+1. Here
the position that earns s+1 is decided at s−1. **So every signal is one session
staler than the paper's (except Calendar₋₄'s, below), and every exposure day
is the paper's.** The Calendar
window is calendar-known (P4). The Threshold part therefore loses the paper's
strongest day, day 1. Fig. 4 shows pressure still building to day 4
(Threshold) and day 2 (Calendar). A same-day variant, with signals from 15:50
prices and MOC the same day, is **not** this trial.

**Which sessions each Calendar component earns: a declared reading [U]
(revision 3).** The paper does not say. Write Eₘ = E for the old month's last
session and D1, D2 for the new month's first two.

- **In the paper,** a position set at the close of s earns s+1. The week4
  component is set on the five sessions E−4 … E, so it earns **E−3 … D1**.
  The Calendar₋₄ component is set on D1, so it earns **D2**.
- **Here the same exposure days are kept.** The week4 component sits in `H`
  on E−5 … E−1, each with sign(−Calendar) one session staler than the
  paper's. The Calendar₋₄ component sits in `H` on E. Its value, Calendar at
  E−3 (the reading above), is known by E, so that component is the paper's
  exactly.
- **The alternative reading,** in which the week4 component earns the week4
  sessions themselves (E−4 … E), **is not run.**

**Windows.** Fit from 2002-08-30 to 2022-12-30, 20.3 years.

- **Every fit year lies inside the paper's sample** (1997-09-10 → 2023-03-17),
  so the fit is a replication on ETFs under shift(2).
- **The holdout from 2023-03-18 is the only part after the paper's sample.** It
  is reported as its own row.
- **The paper finds the effect significant only from the early 2000s** (p.4).

**D4 sets (two regressions, both must pass).**

- MKT and TERM, over the full fit.
- MKT, TERM, HY and IG, from 2007-04-12. This one binds (§2.2 Table C).

**Reported regressions.**

- **R-FF.** HMM's own alphas are on CAPM, C4, FF5 and HXZ, Table 6 Panel B.
- **R-AQR** on TSMOM and VME MOM.

**Decision table.**

| stage | statistic | rule | if it fails |
|---|---|---|---|
| 1 | sized gross Sharpe; NW t | t ≥ 1.96 (the plan's "95% band around zero") | KILL D1 |
| 2 | **BIL/SHY control** (revision 3): H = {BIL: +w, SHY: −w} with X2's own w, sized by P5, turnover-matched by construction. SHY sits in IEF's slot, so the control's duration sign matches X2's IEF leg; BIL, near-zero duration, sits in SPY's. Revision 2's "the same w on SHY − BIL" put SHY in SPY's slot, so its duration sign was the opposite of X2's. **Both Sharpes are computed on the window from BIL's first return, 2007-05-31, to 2022-12-30** (3,926 sessions, 15.58 yr [V: `slate_feasibility.py`]) | **KILL if the control's gross Sharpe ≥ ½ × X2's** on that window | KILL D1: not rebalancing pressure |
| 3 | placebo (decides); shift(3) (reported, §1.8) | §1.8 | KILL D1 |
| 4 | R-D4, both regressions | alpha t ≥ 3.0, \|β\| ≤ 0.10 | KILL D4 |
| 5 | `_dsr`, N = 5 | > 0.95 | NEITHER |
| 7 | holdout sign; post-2023-03-18 row reported | as fit | KILL D3 |
| 8 | net at 15bp | > 0 | D2 label |

**Diagnostics** (reported, never kills):

- the Calendar part with a mid-month placebo window (sessions 6–10);
- 1,000 seeded permutations of the Calendar part's monthly signs;
- correlation with X3;
- **the alpha of X2's week4 component on X3's sleeve** (revision 3): the
  week4 component's daily P&L regressed on X3's sized sleeve, HAC with
  L = 21, alpha in %/yr with its t. The week4 component holds IEF, long or
  short, in the same last sessions in which X3 is long IEF, so this shows how
  much of X2's Calendar part is the month-end Treasury extension. It needs
  X3's series (§1.12).

**Turnover and costs** [arithmetic, raw scale].

- **The Calendar part alone** moves w by about 2 units a month on two legs:
  about 48 one-way turns a year. That is a drag of at least 240 / 720 / 1,440
  bp/yr at 5 / 15 / 30bp. The Threshold part adds to this.
- **Against the published gross** of 10.20%/yr at 9.17% vol (Table 6), the
  sign flips by 30bp even with the effect intact.
- **SPY and IEF trade inside the CEF-calibrated grid** [U: not measured; plan
  items 0.2 and 0.5].

**Expectation** [U]: a gross Sharpe of 0.2–0.8, below the published 1.11
because day 1 is lost. Positive skew if the effect is there. P(pass) across
that range is 0.006 / 0.118 / 0.566 (§2.2).

**Reverse once trading (H11).**

- **Fidelity, daily.**
- **Reversal at 252 sessions:** reverse if the live gross Sharpe is below the
  5th percentile of the trial's own overlapping 252-session Sharpes,
  re-measured.
- **Drawdown:** the same rule as X1.

**Divergences.**

- Futures carry no distributions; the ETF legs pay and owe them, inside CRSP
  `ret`.
- `late_market` on paper.
- No auction-print line until plan item 0.2.

---

## 6. X3 — month-end Treasury extension

**Mechanism and the other side.**

- **The buyers.** Benchmark-relative holders buy duration at month-end.
  Insurers buy the securities added to the Bloomberg Barclays US Treasury
  Index, which rebalances on the final trading day (H&S §5.2, pp.18–20).
- **The effect.** "The entire term premium is concentrated in the last few
  days of the month" (p.21).
- **Since 2020,** last-day benchmark volume is about 46% above normal and price
  impact about 28% lower. The NY Fed authors conjecture that passive funds
  rebalancing to month-end indices drive it (§12i [V]).
- **Why they persist:** their tracking error is measured against an index that
  rebalances on that day.

**Instruments.** IEF, long only.

**Published parameters, verbatim, and how they map.**

| parameter | published | source | applied here |
|---|---|---|---|
| trade | buy "t trading days before the end of the month", sell "on the last day of the month (at the close of business)" | §2.1, p.4 | long IEF from the close of E−3 to the close of E (earning E−2, E−1, E); `H.loc` = 1 on E−4, E−3 and E−2, decided early (P4) |
| t | **3**: the paper's worked example; excess return largest over 3–5 days (p.5), Sharpe best over 2–3 days (p.7) | pp.5, 7; Tables 1 and 3, pp.25–26 | 3, inside both of the paper's ranges, taken before any look at our data. The value carries the paper's own selection from its 1–10 sweep |
| maturity | 10-year: 0.25%/month (SE 0.05), Sharpe 0.88 | p.5; Tables 1 and 3 | IEF; its duration is shorter than a 10-year zero [U: IEF duration not fetched]. The Sharpe, not the return, is the comparison |
| financing | excess over GC repo | §2.1, p.4 | excess over DGS3MO (P3) |
| size | a plain long position | §2.1 | raw notional 1; then P5 |

**Windows.**

- Fit from 2002-08-30 to 2022-12-30, 20.3 years. 2002–2018 lies inside the
  paper's sample; **2019–2022 is after it** and is reported as its own row.
- Regime rows are reported, never chosen:
  - T+2 settlement, compliance date 2017-09-05 [S: law-firm memos and a
    Deloitte summary of SEC Release 34-80295; the release itself not fetched];
  - T+1, from 2024-05-28 (§12b [V]).

**D4 sets (two regressions, both must pass).**

- TERM and MKT over the full fit. **TERM is IEF held every day**, the team
  lead's named control: the alpha of this regression is the value of the
  month-end timing over holding IEF all the time.
- TERM, MKT, HY and IG, from 2007-04-12. This one binds (§2.2 Table C).

**Reported regressions.** R-FF; R-AQR on TSMOM^FI.

**Decision table.**

| stage | statistic | rule | if it fails |
|---|---|---|---|
| 1 | sized gross Sharpe; NW t | t ≥ 1.96 | KILL D1 |
| 2 | **IEF on every other session** (H&S eq. 2; Table 1 lower panel: 0.07%/month, SE 0.13; Table 3: Sharpe 0.11), sized by P5, two trades a month as X3 | its gross Sharpe < ½ × X3's | KILL D1: the term premium, not month-end |
| 3 | placebo (decides); shift(3) (reported) | §1.8 | KILL D1 |
| 4 | R-D4, both regressions | alpha t ≥ 3.0, \|β\| ≤ 0.10 | KILL D4 |
| 5 | `_dsr`, N = 5 | > 0.95 | NEITHER |
| 7 | holdout sign | as fit | KILL D3 |
| 8 | net at 15bp | > 0 | D2 label |

**Stated in advance: stage 4 will very probably kill X3** [arithmetic].

- **The beta grows with the window notional.** X3's unconditional TERM beta is
  about the window notional × 3/21 (3 of about 21 sessions). It exceeds 0.10
  for any window notional above 0.7.
- **P5 pushes the notional well above that.** P5 sizes the part-time sleeve's
  **unconditional** volatility to the vol target, so the window notional
  exceeds 0.7 whenever IEF's annualised volatility is below about 22.7% at the
  pinned vol target of 6% (§1.3). That is 0.06 / (0.7·√(3/21)).
- **The cap does not enter the decision** (revision 3). D4's betas are
  measured on the sized, uncapped sleeve. The tradable X3 would be capped at
  1.80 on every window day whenever IEF's volatility is below about 8.8%/yr
  (§1.3), which is why the cap is a reported row only. Revision 2 said "the
  cap limits how high it goes"; that is now true only of the reported row.
- **A TERM-hedged X3 is a new trial** (§1.7). Hedging the window's TERM
  exposure after stage 4 has been seen would be re-specifying a factor after
  the result. If the team lead wants it, it is declared separately, with its
  own trial.
- **The test is still run under ruling 1.** Its stage-1 to stage-3 statistics
  measure whether the month-end flow is there, whatever D4 decides.

**Turnover and costs** [arithmetic].

- **Turnover** is 24 one-way turns a year per unit of window notional: 120 /
  360 / 720 bp/yr at 5 / 15 / 30bp per unit.
- **The published gross** for a 10-year zero is 300 bp/yr, and less for IEF,
  so **net at 15bp is expected to be negative (D2)**.

**Expectation** [U]: a positive gross effect near the published Sharpe in
2002–2018, smaller after it. D4 and D2 failures as stated above. No number is
stated, so §2.2 brackets it from 0.37 (0.42 × published) to 0.88 (published):
P(pass) 0.038 / 0.267 / 0.700 across the bracket.

**Reverse once trading (H11).** Fidelity at every window. Reversal after 36
windows: reverse if the live sum is below the 5th percentile of the trial's own
36-window sums, re-measured.

**Divergences.** As X2. On the paper account its cost record is two
`late_market` fills a month.

---

## 7. X4 — multi-asset trend

**Mechanism and the other side.** As X1, across asset classes. MOP's own
universe covers commodities, equity indices, bonds and currencies (§2). No
currency leg is added: the plan lists none, and adding one now would be
choosing.

**Instruments.** X1's nine plus SPY, EFA, EEM, GLD and DBC.

**Published parameters.** X1's table, unchanged. The breadth rule is
≥ ⌈14/2⌉ = 7 eligible, which first holds on **2005-11-30** (SPY, EFA, LQD, IEF,
TLT, EEM, GLD).

- **The decision is on the combined sleeve only.**
- **Rows by asset class are printed and never selected from** (agenda A4).
- **X1 and X4 are not independent:** X1's names carry 9/14 of X4's equal-risk
  budget. They count as two trials anyway, which is conservative.

**Windows.** Fit from 2005-11-30 to 2022-12-30, 17.1 years.

- **The published comparator** is BSV's multi-asset trend: 1.09 in
  replication, 0.98 out of sample (Tables II and IV, pp.42 and 44).
- **It is an upper reference only.** It is an equal-volatility composite of
  four asset classes over many markets, FX included.

**D4 sets (two regressions, both must pass).**

- MKT, TERM, COMMOD, GOLD, INTL and EM, over the full fit. INTL and EM are
  spreads over SPY (§1.7, revision 3).
- The same plus HY and IG, from 2007-04-12. This one binds (§2.2 Table C).

**Reported regressions.** R-FF; R-AQR on TSMOM, TSMOM^EQ and TSMOM^CM;
R-LONG.

**Decision table, turnover, H11 and divergences.** As X1. The TSH control is
built on X4's universe.

**Expectation** [U]: a gross Sharpe of 0.4–0.8. P(pass) across that range is
0.037 / 0.168 / 0.446 (§2.2). BSV's 0.98 would give 0.728, but it is an upper
reference only.

---

## 8. X5 — cross-sectional fixed-income momentum

**Mechanism and the other side.** The same under-reaction as X1, expressed as
relative strength across fixed-income ETFs: long the 12-1 winners, short the
losers. **BSV find the trend factors "subsume the momentum factors" (p.23),**
so X5 must show alpha beyond X1 (R-SPAN).

**Instruments.** X1's names less MUB (not shortable): HYG, LQD, IEF, TLT, EMB,
PFF, BKLN, CWB. The ladder control is SHY, IEI, IEF, TLH and TLT.

**Published parameters, verbatim, and how they map.**

| parameter | published | source | applied here |
|---|---|---|---|
| signal | "the 12-month-minus-1-month excess return" | BSV App. A.I, p.52; AMP §I.B, pp.936–937 | compounded excess return from E₍ₘ₋₁₂₎ to E₍ₘ₋₁₎ |
| weights | zₜ(Rank(Sᵢₜ) − (Nₜ+1)/2); at least two markets | BSV App. A.II, p.54; AMP eq. 1, p.938 | zₜ sets one dollar long and one dollar short (AMP) before sizing |
| sizing | each position over its 3-year rolling volatility of monthly data, floored at the larger of the cross-section's 10% quantile and 2.5% | BSV pp.54–55 | as published, from 36 monthly excess returns |
| factor scaling | a 10-year rolling window to 10% ex-ante volatility | BSV p.55 | **cannot be applied**: there are not ten years of factor history before 2020. P5's fit-window constant takes its place |
| rebalance | monthly | BSV p.55 | at each Eₘ, under H1 |
| start | — | — | ≥ ⌈8/2⌉ = 4 eligible: **2010-03-31** |

**Windows.** Fit from 2010-03-31 to 2022-12-30, 12.7 years.

**D4 set.** MKT, TERM, HY and IG.

**Decision regression R-SPAN** (§1.7): X5's sized sleeve on X1's sized sleeve
plus D4's four factors.

**Reported regressions.** R-FF; R-AQR on MOMLS_VME_FI and TSMOM^FI.

**Decision table.**

| stage | statistic | rule | if it fails |
|---|---|---|---|
| 1 | sized gross Sharpe; NW t | t ≥ 1.96 | KILL D1 |
| 2 | **Treasury ladder**: the identical rule on SHY, IEI, IEF, TLH and TLT, sized by P5. **Breadth ≥ ⌈5/2⌉ = 3 eligible with 36 months** (X5's rule on five names): its first decision is 2005-07-29 and all five are eligible from 2010-01-29 [V: `slate_feasibility.py`, 2026-10-13]. **Both Sharpes are computed on X5's P&L window, 2010-04-05 → 2022-12-30**, on which all five ladder names are eligible. Turnovers printed; the comparison is gross Sharpe (revision 3 declares the window and breadth; revision 2 gave neither) | its gross Sharpe < ½ × X5's | KILL: duration timing (closed) |
| 3 | placebo; shift(3) (both decide) | §1.8 | KILL D1 |
| 4 | R-D4; **R-SPAN** | R-D4 as §1.7; R-SPAN alpha t ≥ 1.96 | KILL D4; KILL "spanned by trend" |
| 5 | `_dsr`, N = 5 | > 0.95 | NEITHER |
| 7 | holdout sign | as fit | KILL D3 |
| 8 | net at 15bp | > 0 | D2 label |

**Why the ladder is not turnover-matched (H2; revision 3).**

- H2 exists because, within one signal, a faster construction looks better
  gross and worse net.
- Here the rule is identical and only the universe differs, so a turnover
  difference measures how fast the ranks move in each universe. It is not a
  construction choice.
- Matching would mean altering the rule on one universe (a band, or a slower
  refresh). The control would then no longer be the identical rule, which is
  what makes it a control.
- **Reported beside the gross comparison, never deciding:** both turnovers and
  both net Sharpes at 5, 15 and 30bp, each charged its own turnover.

**Turnover.** No measured relative exists; the figure is printed at Stage 0b.

**Expectation** [U]: a gross Sharpe of 0–0.4. The published 0.29 has t 1.61
in replication (Table II). P(pass) across that range is < 0.001 / 0.003 /
0.022 (§2.2).

**H11 and divergences.** As X1.

---

## 9. Reading the results: power, ranked by what each test can teach

All five run (ruling 1). This ranking does not cut anything. It says before any
result exists how much each outcome would teach. **Restated in revision 3** at
the draft's own expected Sharpes (§2.2); revision 2 ranked at the published
Sharpes and read X2 as powered (P = 0.94) and a fail of X2 as closing it. Both
are withdrawn. Ranked by P(pass) at the midpoint of each expected range.

| test | P(pass) at the draft's expected low / mid / high | at the published Sharpe (upper reference) | a pass would mean | a fail would mean |
|---|---|---|---|---|
| **X3** | 0.04 / 0.27 / 0.70 (bracket; §6 states no number) | 0.70 | the month-end Treasury flow is there on IEF; **but D4 very probably kills it** (§6) | most likely a D4 kill by construction. Stages 1–3 still measure the flow |
| **X4** | 0.04 / 0.17 / 0.45 | 0.73 (a many-market composite) | ETF-implementable multi-asset trend clears a deflated bar and is not beta | little on its own: powered only near the top of its range. Evidence only against Sharpes near 1.04 |
| **X2** | 0.006 / 0.12 / 0.57 | 0.94 (in-sample, futures, no shift(2) delay) | a mandate-driven flow survives a one-session delay on ETFs, with a post-publication holdout | little on its own: powered only at the top of its range. Evidence only against Sharpes near 0.95. It does not close the mechanism |
| **X1** | 0.01 / 0.04 / 0.13 | 0.06 | strong evidence, against the odds | almost nothing: underpowered at 14.65 years |
| **X5** | < 0.001 / 0.003 / 0.02 | 0.01 | strong evidence, and alpha beyond trend | almost nothing; and the paper expects it spanned |

## 10. Trial accounting

- **XASSET today: 0 trials.** On approval N = 5 is fixed. The trials-used
  column never moves at approval.
- **When it moves (revision 3; revision 2 said "in the same commit as each
  run"):** k−1 → k in a commit made after Stage 0a's hash commit and before
  that test's Stage 0b computes anything (§1.11). A test left UNRUN at Stage
  0a spends no trial, and N stays 5.
- **`docs/RESEARCH_STATE.md` changed in this commit (revision 3): no.**
  XASSET stays 0.
- **No other counter moves.** CEF, EVENTS and GAMMA are untouched. The 27-name
  holdout is not consumed (P14). The 2023-01-01 time holdout (2023-01-03 →
  2026-09-30) stays sealed until **all five** fit verdicts are committed
  (§1.5).
- **Sources:** `docs/REFERENCES.md` §12i, which holds the paper parameters, the
  feasibility snapshot, the AQR files and the inference methods. The DGS3MO row
  is in §8. The §12b rows were amended in place.
- **Zero-trial script:** `scripts/xasset/slate_feasibility.py`, with tests in
  `scripts/xasset/tests/`.
- **Revision history:**
  - Revision 1 (commit `0d7474d`) was the first draft.
  - Revision 2 (commit `af61e28`) applied the four rulings in §0.1 and added:
    - CRSP-primary data and the quality screen;
    - P5 sizing;
    - HAC and bootstrap inference;
    - power;
    - the R-D4 / R-FF / R-AQR / R-SPAN regressions;
    - the signal placebo;
    - a common order of evaluation;
    - the declared Calendar₋₄ reading.
  - Revision 3, this one (2026-10-13, branch `fix-xasset-review`), applies the
    adversarial review's nine fixes, listed at the top of this note.

---

## 11. Decisions that remain the team lead's

Revision 3 applies the review's fixes as written. These remain open, and each
is the team lead's to take **before approval**, since after it nothing in this
note changes:

1. **Approval itself**, which fixes N = 5 and the declarations in §0, §4–§8.
2. **The pinned spec hash** (§1.3). If the frozen spec changes before
   approval, the approval names the hash it pins.
3. **The holdout end, 2026-09-30** (§1.5; the review's date). Any other date
   must be fixed now, before any run, never after.
4. **Stages 7 and 8 on the sized sleeve.** The review named stages 1–3 and 5;
   this note extends the sized, uncapped series to the holdout sign and the
   net-at-15bp label, so one series decides throughout. The alternative is to
   read stage 8 (a real-money view) on the tradable sleeve.
5. **UNRUN counts as a committed fit verdict** for opening the holdout (§1.5).
   Without this, one test blocked at Stage 0a would seal the other four
   holdouts indefinitely.
6. **The X2 readings, all [U]:** Calendar₋₄ as the Calendar signal at E−3
   (revision 2); the exposure days, week4 earning E−3 … D1 and Calendar₋₄
   earning D2; and the Threshold portfolios starting at 60% at the close of
   2002-07-29 (§5). The alternatives are not run.
7. **X3's expected Sharpe.** §6 states none; §2.2 brackets it. A number stated
   now changes only how a null is read, never a decision.
8. **What counts as the independent third source** for a Stage 0a repair
   (§1.1).
9. **A TERM-hedged X3** (§6): a new, separately declared trial, or not at all.
10. **Already the team lead's under revision 2, unchanged:** WATCH or D5 for a
    NEITHER (stage 5); paper-only for a D2 (stage 8); and any Stage 0a halt.
