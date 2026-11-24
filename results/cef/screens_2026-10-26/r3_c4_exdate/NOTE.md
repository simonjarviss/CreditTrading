# R3: is C4's ex-date P&L concentration real, or an artifact? (zero trials, report only)

Asked by the team lead, 2026-10-26. **No trial is spent and no counter moves.** Fit window only
(every return, IC and P&L is dated on or before 2022-12-30, asserted in code). The 2023-01-01
holdout stays sealed. Holdout figures below are copied from the committed note and labelled [doc].
Gross only; there is no cost grid, at the team lead's request.

## 0. The question

C4 (CEF trial 52) puts **33.1%** of its fit P&L in the ex-date window [0,2], on **10.5%** of held
gross fund-days [doc, C4_RESULT §7]. In the holdout as first committed the share was 82.1% on 12.5%
[doc]. With the four bad IGR bars corrected it was **52.6%** [doc, §8]. Is the concentration a real,
tradable price effect, or does a mechanical or data cause explain it? And what does it mean for C4
on Alpaca paper, which credits no distribution on a long and charges none on a short?

---

## 1. DECLARED DESIGN, written 2026-10-26 before any result was computed

Nothing below has been computed yet. Before this section was written, the only things looked at
were schemas, date ranges and the row counts of the disagreement files. No P&L, IC or window share
had been computed.

### 1.1 Data and machinery (reused, not rebuilt)

- **Code.** `scripts/cef/c4_families.py` at `simon` dff4b5c (SCRATCH/tree), imported unchanged:
  `universes`, `qqqx_rule`, `crsp_pivot` (with its identity and calendar checks), `build_book`,
  `fit_slice`, `run_book`, `check_held`, `crsp_ex_dates`, `ex_window_mask`, `ex_window_split`.
  Also `band_frontier.evaluate` / `band_gross_capped` / `build_targets` / `total_returns`, and
  `w4_artifacts.nw_t`. The only new code is the bookkeeping that splits P&L by window and by event.
  It is not a backtester. Every P&L cell is `evaluate()`'s own `H.shift(2) * R`, and the parts are
  asserted to sum to `evaluate()`'s P&L.
- **Panels truncated before use.** The families price and NAV panels (`data/cef_families/`, last
  date 2026-10-09), and the live core panels (`data/cef/`), are copied to this folder cut at
  2022-12-30. `c4.FAM_SRC` is pointed at the copies. The signal is causal: the z-score's μ and σ
  and the ADV are `.shift(1)`, the repeat mask is a diff with the previous row, and the band is
  sequential. So the fit rows are unchanged.
  - **Amended before any result, on the first run.** `build_targets` raised on the truncated
    families panel, because the nine funds without pre-2023 data (BSTZ, BTX, GUG, HGLB, IGA, KYN,
    NPFD, NXG, TBLD) then have no column. So the C4 book is built exactly as the committed fit
    builds it: `build_targets` on the full families panel (causal, H7), then `fit_slice` at
    2022-12-30 before the band, the cap and `evaluate()`. No 2023+ return reaches any statistic;
    `_assert_fit` checks every frame. The truncated copies are still used for this screen's own
    reads (NAV returns, closes, volumes) and for the core book.
  - **Gate:** the declared book must reproduce the
  committed fit gross Sharpe 1.216957834377122 to 1e-9, and the window split must reproduce 33.1%
  / 10.5%. Otherwise the run stops.
- **CRSP returns.** The C4 cache is gitignored and absent from the export, and restaging it needs R2,
  which is forbidden here. It is therefore read from the `trial-c4` worktree's
  `results/cef/c4/_cache_c4/crsp_ret_families.parquet` (staged 2026-10-15 by
  `stage_crsp_cef_families.py --returns`; sha256 recorded in the output). It is read read-only,
  with a parquet filter `date <= 2022-12-30`, so no 2023+ CRSP row is ever loaded. CRSP values are
  never written to disk; the outputs hold aggregates and counts only.

### 1.2 The book and the two return bases

- **The book.** The declared C4 book: the 74 frozen funds, the spec's live z-score, the band at
  4.8% traded to the edge, the gross cap at 1.80. All through `run_book`.
- **Total** = CRSP `ret` (the fit's own primary return).
- **Price-only** = CRSP `retx` on the *same* holdings H. This is what Alpaca paper books: no
  distribution is credited on a long and none is charged on a short.
- **Distribution leg** = total − price-only = H.shift(2)·(ret − retx). It is non-zero only on CRSP
  ex-dates, so it falls entirely on window day 0. On a short it is the payment in lieu, which paper
  never charges.

### 1.3 The window, events and statistics

- **The window [0,2].** Amendment 3's definition: CRSP ex-dates are the fund-days with
  `ret != retx`. A fund-day is in the window if it is the ex-session or one of the next two
  sessions.
- **Event ownership.** Each window fund-day belongs to the latest ex-date at or before it.
- **Per window W, on each basis:**
  - S = in-window P&L ÷ all P&L.
  - G = in-window held |weight| fund-days ÷ all held |weight| fund-days.
  - **CR = S / G**, the concentration ratio.
  - The excess series e_t = inw_t − ρ_out·gW_t, where ρ_out is the out-of-window P&L per unit of
    out-of-window held gross. It measures what the window earns beyond the book's rate elsewhere.
    Its **NW t (L = 21)** is reported.
  - Annualised in-window and rest P&L.

### 1.4 Negative control (declared first)

- **Placebo windows.** Every CRSP ex-date is shifted by **+5** and by **−5** sessions, positionally
  on the session index. A [0,2] window is laid from each shifted date. Any fund-day inside a real
  window is removed from the placebo.
- **Reported:** S, G, CR and the excess t, for +5, −5 and pooled ±5, on both bases.
- **Pre-declared reading.** The concentration is ex-date specific only if the real window's
  total-return CR exceeds the pooled placebo CR.
- **Contrast: the deployed 13-name core book** (spec v7 universe, `book_series`' construction: the
  live panel, band to the edge, gross-capped). Its own fit runs from its first held session
  (2013-06-21 expected) to 2022-12-30. Its ex-dates come from `data/cef/cef_distributions.parquet`,
  its own total-return source. Same S, G, CR and placebo, on both bases (price = `build_targets`' R;
  total = `total_returns(R)`).

### 1.5 Explanation 1: price/NAV ex-date misalignment

**Events.** Every CRSP ex-date of the 74 from 2005-01-03 to 2022-12-30 on a fund with NAV data.
Counts are reported for all events and for held events (held gross > 0 on any owned window day).

**Per-event inputs:**
- y_e = ret − retx: the distribution over P_{t−1}, from CRSP.
- q_e = −y_e · close_{t−1}/NAV_{t−1} (yfinance, the same share basis): the expected NAV return on
  the drop day.
- **NAV returns** r^N on the session index at s−1, s and s+1, where s is the ex-session. Consecutive
  sessions are required. NAV missing on any of s−2 … s+1 makes the event *unmeasurable*.
- **Peer adjustment.** u = r^N − the median r^N of same-family pool funds that day. The median
  excludes the fund itself, any peer with a CRSP ex-date within ±1 session of that day, and any peer
  whose NAV repeats exactly that day (r^N = 0, a stale copy). This clarification was added before
  any computation. At least 3 peers are required; otherwise the event is *unmeasurable*. No fallback
  to raw returns is used.
- **σ_e.** The sd of u over sessions s−64 … s−2, which ends before the event (no lookahead). It
  excludes sessions within ±1 of any of the fund's ex-dates and NAV repeats (r^N = 0). At least 40
  usable values are required; otherwise the event is *unmeasurable*.

**Classification.** Gaussian log-likelihoods, with the drop q_e landing at offset k and zero
elsewhere:
- LL_k = −[(u_k − q_e)² + Σ_{j≠k} u_j²] / 2σ² for k ∈ {−1, 0, +1};
- LL_none = −Σ_j u_j² / 2σ².

The class is the argmax **if it beats the runner-up by ≥ 2 log-units** (likelihood ratio ≥ e²).
Otherwise the event is AMBIGUOUS.
- **0** = aligned.
- **+1** = the NAV lags the price.
- **−1** = the NAV leads the price.
- **none** = no drop within ±1.

**Reported beside it:**
- **Deterministic count:** the yfinance NAV repeats exactly on the ex-session (stale on the ex-date).
- **Second method, an independent dated source:** CEFConnect's weekly `All` NAV, through
  `nav_flags.cc_nav_All` on s−1 … s+1. Among event-days with a CEFConnect row, the counts of AGREE,
  SHIFT_PREV, SHIFT_NEXT, A_REPEATED and UNEXPLAINED.
- **Third, aggregate method:** pooled OLS of u_{s+k} on q_e for k = −2 … +2 over the measurable
  events. β_k is the share of the drop landing at k. Aligned on aggregate means **β_0 ≥ 0.8 and
  |β_{±1}| ≤ 0.2**. The same regression on CRSP `retx`, peer-adjusted the same way, is the price's
  reference.

**Share of in-window P&L by class**, on both bases, with each class's CR.

**Explanation 1 explains the concentration if:**
- events classed −1, +1 or none carry ≥ 50% of in-window total-return P&L; **or**
- the aligned class's CR ≤ the pooled placebo CR.

If AMBIGUOUS and unmeasurable events carry > 50% of in-window P&L, the class test cannot decide, and
the pooled-slope criterion decides instead.

### 1.6 Explanation 1b: stale prints (the desk's most common cause of death)

- **Flag.** A window fund-day is *stale-print* if CRSP `prc` ≤ 0 (no closing trade; CRSP's bid/ask
  average) on t or t−1, or if the yfinance volume is 0 on t or t−1.
- **Reported:** the share of in-window P&L on those fund-days, against their share of in-window
  gross.

### 1.7 Explanation 2: total-return against price-only accounting

**Reported:** S, G, CR and the excess t on both bases. The in-window price-only P&L is split exactly
into:
- the in-window total-return P&L, and
- the mechanical transfer, −Σ held·y on day 0.

Each part is shown by window day k = 0, 1, 2 and by held side (long or short).

**Reading:**
- The **economic** price effect is the total-return in-window P&L: the price move net of the cash
  that real money pays or receives.
- The **paper** view is the price-only P&L.
- If the total-return CR ≤ the placebo CR while the price-only CR > the placebo CR, the
  concentration on paper is the distribution transfer: **ARTIFACT (accounting)**.

### 1.8 Explanation 3: disputed distribution amounts

- **The amendment rulings.** All 71 disputed ex-dates are dated 2025–26 (to be asserted), so they
  touch **no fit event**. Moreover, the fit's P&L reads no distribution amount except CRSP's own,
  and the signal reads none.
- **Fit-window disputes, per event, flagged if any of the following holds:**
  - **(a) CRSP against yfinance amount.** y_yf = D_yf / close_{t−1}. The event is disputed if
    yfinance has no dividend on that date, or if |y_crsp − y_yf| > 0.001/close_{t−1} + 2e-6
    (amendment 2's $0.001, plus CRSP's 6-decimal rounding).
  - **(b)** a `nav_disagreements.csv` row for the fund on s−1 … s+2.
  - **(c)** a `discount_disagreements.csv` row on s−1 … s+2.
  - **(d)** a `price_disagreements.csv` row (yfinance close against CRSP) on s−1 … s+2.
- **Reported:** the share of in-window P&L, on both bases, carried by each flag and by their union,
  beside the share of in-window gross they carry.
- **Explanation 3 explains the concentration if** the union carries ≥ 50% of in-window total-return
  P&L **and** the undisputed events' CR ≤ the placebo CR.

### 1.9 Verdict mapping (declared)

- **Data-cause share D%:** the share of in-window total-return P&L on events that are classed
  misaligned (−1, +1, none), **or** carry any dispute flag (a)–(d), **or** sit on a stale-print
  fund-day.
- **CR_clean:** the concentration on the complement.

**ARTIFACT** (the cause is named) if any of these holds:
- (i) the real window's total-return CR ≤ the pooled placebo CR: not ex-date specific (or, if only
  price-only beats the placebo, the accounting transfer);
- (ii) D% ≥ 50%;
- (iii) CR_clean ≤ the pooled placebo CR.

**REAL** if all of these hold:
- the total-return CR > the pooled placebo CR;
- the excess NW t ≥ 2.0;
- D% < 20%;
- CR_clean > the placebo CR;
- the in-window price-only P&L > 0;
- if AMBIGUOUS and unmeasurable events carry > 50% of in-window P&L, the pooled slope says aligned.

**MIXED** otherwise. The note then states what share is which. This includes:
- a D% between 20% and 50%;
- a concentration above the placebo whose excess t is < 2. This case is reported as "MIXED:
  concentration not established".

**INFEASIBLE** if the gate in §1.1 cannot be met.

### 1.10 Descriptive only (declared now; it decides nothing)

- The event-time profile of P&L per unit of held gross at offsets −10 … +12 around CRSP ex-dates,
  on both bases.
- In-window P&L by family.
- The mean signed held weight on ex-sessions: is the book net short the distribution?

---

## 2. Results (run 2026-10-26)

Every figure is [V], computed by `exdate_screen.py` (declared, §2.1–2.6) or by `exdate_posthoc.py`
(added after the declared run, §2.7), unless it is labelled [doc]. "%" of P&L means a percent of
capital, summed over the fit.

**Panels and their last dates:**
- families prices and NAV: cut at 2022-12-30 for this screen's reads; the C4 book is built on the
  full panel (last date 2026-10-09) and cut by `fit_slice`;
- CRSP: filtered to ≤ 2022-12-30 (cache sha256 `47f20b47…`, staged 2026-10-15);
- the core book's panels: cut at 2022-12-30.

**Gate: PASS.**
- The fit gross Sharpe is 1.216957834, equal to the committed 1.216957834. It runs
  2005-02-22 → 2022-12-30, over 4,497 sessions.
- The amendment-3 window share is 33.11% on 10.54% of held gross, against the committed 33.1% and
  10.5% [doc].
- Price-only on the same H gives Sharpe 1.360 and 8.33%/yr, equal to the committed R-P row [doc].
  Total gives 1.217 and 7.16%/yr.

### 2.1 The window and the negative control (C4 fit, the 74)

| window | basis | S (P&L share) | G (held gross share) | CR = S/G | in-window P&L | excess NW t |
|---|---|---:|---:|---:|---:|---:|
| **real [0,2]** | **total** | **33.1%** | 10.5% | **3.14** | +42.34% | **+2.38** |
| placebo +5 [5,7] | total | 13.4% | 10.3% | 1.30 | +17.16% | +0.42 |
| placebo −5 [−5,−3] | total | 19.4% | 10.5% | 1.85 | +24.83% | +1.04 |
| **placebo pooled ±5** | **total** | 31.8% | 20.8% | **1.53** | +40.68% | +1.14 |
| **real [0,2]** | **price-only (paper)** | **42.5%** | 10.5% | **4.03** | +63.11% | **+3.70** |
| placebo pooled ±5 | price-only | 27.4% | 20.8% | 1.32 | +40.68% | +0.79 |
| core 13, real [0,2] | total | 20.1% | 14.7% | 1.37 | +11.91% | +0.39 |
| core 13, placebo pooled ±5 | total | 55.2% | 28.5% | 1.94 | +32.65% | +1.68 |
| core 13, real [0,2] | price-only | 22.8% | 14.7% | 1.56 | +13.95% | +0.54 |

**Reading the table:**
- **Rest of the book.** On the total basis, the fund-days outside the window earn +4.79%/yr
  (Sharpe 0.814). The window earns +2.37%/yr (Sharpe 0.774).
- **Second excess.** Against the baseline rate (outside both the real and the placebo windows), the
  real window's excess t is +2.61 and the pooled placebo's is +1.74.
- **The core book.** The 13-name core runs 2013-06-25 → 2022-12-30. It has total Sharpe 0.955 and
  price-only 0.959. **It shows no ex-date concentration: its placebo beats its real window.** That
  is consistent with W4 [doc].

### 2.2 Explanation 2: total-return against price-only accounting

**The distribution leg (total − price-only)** over the fit is **−20.77% (−1.16%/yr)**. The book is
net short distributions on ex-days: mean signed weight −0.0025.

| window day | total | price-only | distribution leg | held gross share |
|---|---:|---:|---:|---:|
| 0 (ex-date; earned by the decision of s−2) | +13.15% | +33.92% | −20.77% | 3.5% |
| 1 | +4.28% | +4.28% | 0 | 3.5% |
| 2 (earned by the decision of s itself) | **+24.92%** | +24.92% | 0 | 3.5% |
| **in-window, long** | −22.32% | −116.39% | +94.06% | 4.7% |
| **in-window, short** | **+64.66%** | +179.50% | −114.84% | 5.9% |

**The window's P&L is earned by shorts.** By day [V, post-hoc P2]:
- short positions make +19.64%, +22.00% and +23.02% on days 0, 1 and 2;
- longs lose −6.49% and −17.73% on days 0 and 1.

**The event-time profile** (P&L per unit of held gross, bp/day; the book's average is 2.13):
- day 0 is +6.3, and +16.1 on price-only;
- day +2 is +11.8, the largest offset in −10 … +12;
- placebo offsets range from −1.3 to +7.8.

**By family.** In-window total P&L is concentrated in equity CEFs: covered-call +21.65%, sector
+16.61%, multi-asset +5.82%, domestic +1.24%, preferred −2.99%.

### 2.3 Explanation 1: price/NAV ex-date misalignment

7,985 CRSP ex-dates of the 74 in 2005–2022 on funds with NAV; 3,977 held.

| NAV class | all | held | share of in-window total P&L | price-only | in-window gross | CR |
|---|---:|---:|---:|---:|---:|---:|
| 0 (aligned) | 3,034 | 1,576 | 53.2% | 62.0% | 44.7% | 3.74 |
| +1 (NAV lags) | 91 | 43 | 10.0% | 6.8% | 1.2% | — |
| −1 (NAV leads) | 42 | 18 | −1.0% | −1.0% | 0.2% | — |
| none | 54 | 27 | 2.7% | 1.2% | 0.5% | — |
| ambiguous | 3,507 | 2,097 | 28.9% | 31.2% | 48.8% | 1.86 |
| unmeasurable | 1,257 | 216 | 6.2% | −0.1% | 4.8% | 4.11 |
| **misaligned (+1, −1, none)** | 187 | 88 | **11.7%** | 7.0% | 1.8% | — |

- **Separability.** The median |drop|/σ is 1.84, which is why many events are ambiguous.
- **Held unmeasurable events, by reason:** peers < 3 (138), σ < 40 values (76), NAV missing (2).
- **Deterministic count.** The yfinance NAV repeats exactly on the ex-session on 526 events (139
  held).
- **Second method: CEFConnect's dated weekly NAV** on s−1 … s+1. 4,023 event-day rows have a
  CEFConnect value; 3,922 AGREE (97.5%). There are 14 SHIFT_PREV or SHIFT_NEXT, 31 A_REPEATED, 53
  UNEXPLAINED and 3 SPLIT_ADJ.
- **Third method: pooled slope** of the peer-adjusted NAV return on the expected drop.
  - **β0 = +1.032** (se 0.014). The other slopes are β−2 +0.013, β−1 −0.026, β+1 −0.001 and
    β+2 +0.000.
  - **Aligned on aggregate**, by the declared β0 ≥ 0.8 and |β±1| ≤ 0.2.
- **The price, by the same method, drops 1.029y on the ex-date.** It rises before it (β−1 −0.083,
  β−2 −0.039) and **keeps falling after it (β+1 +0.137, β+2 +0.074)**, while the NAV does not.
  That is a post-ex price drift, which W4 also found on the core [doc].

**Explanation 1b, stale prints.** Two in-window fund-days carry 0.0% of in-window P&L.

### 2.4 Explanation 3: disputed amounts

**The amendment-4 rulings.** All 71 disputed ex-dates fall between 2025-01-14 and 2026-08-20, so
**0 are in the fit** (asserted).

| flag (event, s−1 … s+2) | events (held) | share of in-window total P&L | price-only | in-window gross |
|---|---:|---:|---:|---:|
| (a) CRSP vs yfinance amount | 788 (449) | 0.7% | 9.7% | 14.1% |
| (b) NAV disagreement (CEFConnect) | 147 (84) | 1.3% | 0.8% | 2.0% |
| (c) discount disagreement | 128 (71) | 0.2% | 0.4% | 1.7% |
| (d) price disagreement (yfinance vs CRSP) | 203 (34) | 0.8% | 0.1% | 0.7% |
| **any dispute** | 1,107 (555) | **2.0%** | 10.9% | 16.6% |
| undisputed | 6,878 | 98.0% (CR 3.69) | 89.1% | 83.4% |

**Flag (a) is yfinance's known defects, not CRSP's** [V, post-hoc P6]. Its yfinance/CRSP yield
ratios have a median of 0.986 (UTF, BUI, SCD and EMO: the ~2% scaling) and 3.0 at the 75th
percentile (IGR's split-adjusted dividends). The fit reads only CRSP's amount.

### 2.5 The declared verdict inputs (§1.9)

| input | value | rule |
|---|---:|---|
| CR, real against pooled placebo (total) | **3.14 vs 1.53** | real > placebo ✓ |
| excess NW t (total) | **+2.38** | ≥ 2.0 ✓ |
| data-cause share D% (misaligned, disputed or stale) | **12.6%** (price-only 16.3%) | < 20% ✓ |
| CR_clean | 3.36 (87.4% of in-window P&L) | > 1.53 ✓ |
| aligned-class CR | 3.74 | > 1.53: explanation 1 does not explain it |
| in-window price-only P&L | +63.11% | > 0 ✓ |
| ambiguous and unmeasurable share | 35.1% | < 50%, so the class test decides (the slope agrees) |

**By the declared rule: REAL.**

### 2.6 What paper does to it

Alpaca paper books price-only P&L: no distribution on a long, no payment in lieu on a short.
- On the fit that gives **Sharpe 1.360 (+8.33%/yr) against 1.217 (+7.16%/yr)**, a gain of +1.16%/yr
  that real money would not keep.
- **The distribution leg is negative in every era** [V, post-hoc P7]: −1.34, −1.26, −0.26 and
  −2.23%/yr.
- **The whole gain lands on window day 0.** On paper the window's share rises from 33.1% to 42.5%,
  and its CR from 3.14 to 4.03.
- **Of paper's in-window +63.11%:**
  - **+20.77% (33%) is the distribution transfer**, an accounting artifact of paper;
  - **+42.34% (67%) is the price effect** that real money also earns.
- Paper also hides large gross flows. In-window longs would have received +94.06% and shorts paid
  −114.84%. So **paper's day-0 P&L per position is not comparable to a live account's.**

### 2.7 Post-hoc checks (added after the declared run; report-only; they cannot change the verdict)

**P1. Where the CRSP price drop lands** (the same likelihood rule; median |y|/σ is 1.10, so 76% of
events are ambiguous).
- Late drops (+1 or +2): 174 events carry 12.7% of in-window P&L on 1.8% of gross.
- **They are not misdated.** yfinance dates all 174 on the CRSP ex-date, and most have an aligned
  NAV (`probe_late_drops.py`). The largest coincide with market shocks: ETW 2015-08-20, whose s+2 is
  2015-08-24.
- Without them the post-ex drift remains: β+1 +0.121 and β+2 +0.064.

**P3. By era (H5): the concentration is a post-2010 effect.**

| era | S | G | CR | excess t | placebo CR |
|---|---:|---:|---:|---:|---:|
| 2005–09 | 15.9% | 9.7% | 1.63 | +0.34 | **3.51** (the placebo beats the window) |
| 2010–14 | 25.1% | 8.8% | 2.84 | +0.78 | 1.84 |
| 2015–19 | 49.5% | 11.8% | 4.19 | +1.78 | 1.00 |
| 2020–22 | 42.3% | 12.4% | 3.41 | +2.01 | 0.06 |

No single era reaches t ≥ 2 except 2020–22. The corrected holdout (2023–26) shows 52.6% on 12.5%
(CR ≈ 4.2) [doc, C4_RESULT §8], which is out-of-sample support. Caveat: the [0,2] window was
designed after the fit was seen (amendment 3), so the fit's t of +2.38 is optimistic.

**P4. Specials (y > 2%)** carry 18.1% of in-window total P&L on 12.5% of in-window gross (31.2% on
price-only).

**P5. Without the 10, 20 or 50 largest events:**

| events dropped | CR | placebo CR | excess t |
|---:|---:|---:|---:|
| 10 | 2.94 | 1.58 | +2.47 |
| 20 | 2.57 | 1.67 | +2.05 |
| 50 | 2.46 | 1.71 | +2.08 |

## 3. Verdict

**REAL**, by the rule declared in §1.9.

**What the effect is.** The concentration is a price effect around the ex-date, in equity CEFs and
mainly from 2010 on:
- the price runs up before the ex-date and drops 1.03× the distribution on it;
- it keeps falling for two sessions while the NAV does not;
- the discount z-score is net short these funds into the ex-date and earns that drift. Shorts earn
  on every window day.

**What it is not:**
- **Not NAV misdating.** NAV β0 = 1.03; misaligned events carry 11.7%; CEFConnect agrees on 97.5%.
- **Not disputed amounts.** They carry 2.0%, and the fit reads only CRSP's amounts.
- **Not stale prints.** They carry 0.0%.

**What softens it:**
- t is only +2.38, on a window chosen after the fit was seen;
- the effect is absent in 2005–09;
- on paper, a third of the window's P&L is the distribution transfer, which real money pays away.

## 4. Reproduce

```bash
cd /private/tmp/claude-501/-Users-simonjarvis-Downloads-2027-Projects-Quant---PM2027-2027/767b4ac8-7cb7-4bf6-953a-b785b037a5b4/scratchpad && python3 r3_c4_exdate/exdate_screen.py && python3 r3_c4_exdate/exdate_posthoc.py
```

Outputs go to `r3_c4_exdate/out/`: `exdate_screen_output.txt`, `exdate_screen_results.json` and
`exdate_posthoc_output.txt`. Together they take about 1 minute. They need the trial-c4 worktree's
CRSP cache (read-only), which is gitignored and comes from R2.
