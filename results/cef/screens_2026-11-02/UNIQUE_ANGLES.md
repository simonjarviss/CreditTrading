# Unique angles: structural and mechanical effects nobody on the desk was measuring (2026-11-02)

**Zero trials. No counter moved** (CEF 53, EVENTS 3, MACRO 0, XASSET 4, GAMMA 0, read from `docs/RESEARCH_STATE.md`
at `862b1d0`). Nothing here touches the live path, a broker or `data/`. **Every return statistic is on sessions on
or before 2022-12-30**: `angle_common.py` copies the four harness panels truncated at that date into `_cache_fit/`
(gitignored) and points `band_frontier.DATA_DIR` at the copy, so no 2023+ price or NAV enters the harness, and
`assert_fit` checks every frame a script reports from. The 27 sealed `cef_universe.csv` names are never loaded.
The book is the unit book of the live policy from the frozen spec (`cef_discount.v8.20261101`, band 4.8% + gmax
1.80x, universe 13); trial 53's ×1.13 is applied only where a line says so. Every figure below is **[V]**
(re-run today by the named script) unless labelled otherwise.

Sibling note: alpha-finder's `ALPHA_SLATE.md` in this folder covers tax-loss, distribution changes, lead-lag,
horizons, the discount level and the event census. Nothing below repeats them.

## The ranking

Ranked by information per trial. Only F asks for a trial; the rest close a question at zero.

| # | angle | verdict | key figures (fit, gross) | counter if pursued |
|---|---|---|---|---|
| **F** | **Turn-of-month price pressure in CEFs** (found while killing a quarter-end "pump and reverse") | **PURSUE to a pre-registration** (a hypothesis found after the fit was seen, not evidence) | Long the 13 names from close k−3 to close k+2 around each month-end, short HYG: **+54.6bp a month, t 5.06** (CRSP, 187 months), median +57bp, 76% of months positive, positive in every era. Placebo 10 sessions earlier **−42.4bp (t −3.28)**. AP-arbitraged ETF control flat. Not equity or HY beta, not an ex-date effect, and not the fund's own DRIP agent | EVENTS (as agenda B3) or CEF; team lead's ruling |
| **A** | The live "NAV drag": predictable, hedgeable, or neither? | **KILL** (ABSENT for the forecast; the hedge raises variance) | The NAV part is unpriced: −0.27%/yr (t −0.36) against the discount part's +6.70%/yr (t 3.29). NAV-lag forecasts known at t predict nothing (t −0.03; second method t 0.43). ETF hedges explain 2–3% of the hold in-sample and **raise** variance out of sample (−9% to −49%) | none |
| **B** | Paper-scoring mechanics: uncredited distributions and late-market fills | **PAPER ARTEFACT** (not alpha); no trading fix | The distribution leg averages −0.21%/yr (t −0.65) on the fit and swings by era. The live +0.32% in 24 sessions is the fit's **94th percentile**, a current long-yield tilt. The late-market fill cost (5.1bp vs close) is the quoted half-spread (6.2bp) less about 1bp of drift | none |
| **C** | Record-date borrow recall in muni CEFs (catalogue row E3), on the IBKR fee history | **KILL as a cost** (closes E3 without waiting for Alpaca snapshots) | Fit: muni log-fee rise around the record date +0.003 (t 0.08), the same as taxable. Present only in 2023–24 (T+2, cost data: +0.055, t 3.10), gone under T+1. At its largest it is about 0.08%/yr of muni short notional | none |
| **E** | Bond-holiday stale NAVs (catalogue row CA9): trades decided on them | **KILL**: closes CA9 | 19 active holidays, 5 with trades, **0.17% of fit turnover**, −0.045% of capital in 9.5 years. Nothing to do on 2026-11-11 | none |
| **D** | Leverage-cost pass-through (the MACRO question) | **KILL** (D1 at zero trials; D7 on episodes) | Muni minus loan discount change per pp of 3-month rate change: +0.61 (t 1.20), the wrong sign; taxable minus loan −0.17 (t −0.26); 12 rate episodes in 18 years | MACRO stays 0 |

**Paper-scoring artefacts, marked:** all of B, and F's hedge leg on paper (HYG goes ex at k+1, so a paper short
books about 42bp a month it would pay in real money; see F). Everything else is about the real-money book.

---

## F. Turn-of-month price pressure (PURSUE)

`angle_quarter_end.py` → `angle_turn_of_month.py`; outputs `angle_quarter_end_output.txt`,
`angle_turn_of_month_output.txt`.

**How it was found, against itself.** The hypothesis tested first was "leaning for the tape": managers push
illiquid CEF closes up at quarter-end, and the price reverts the next session (Carhart, Kaniel, Musto and Reed,
2002 [U: recalled, not fetched]). **It is wrong.** The discount leg (r_price − r_NAV) does rise on the last
session of a quarter (credit 17: +21.5bp over ordinary days, t 3.02), but it rises again the next session
(+24.1bp, t 2.48). There is no reversal. The same shape appears at **every** month-end, and that pattern is
what the rest of this section tests. Because it was found after the fit was seen, it is a hypothesis: the
status `r6_exdrift` had on 2026-10-26.

**Mechanism, and who is on the other side.** CEF prices rise against NAV and HYG from about three sessions
before each month-end to two after, and give it back mid-month. The pay dates fit:
- in CRSP `dsedist` for 2023–24, 16 of the 17 funds pay at the month turn: PIMCO and Nuveen on the 1st, BIT,
  HYT and DSL on the last business day (`exdrift-stage0` cache, `crsp_dsedist_2023_2024.parquet` [V]; pay
  dates only, no return). AWF pays mid-month, around the 19th;
- the ex-dates fall mid-month, from the 9th to the 14th (AWF the 5th).

The candidate buyer is price-insensitive cash at the pay date: brokers' own dividend-reinvestment programmes,
and income holders reinvesting by hand. That is **[U] speculation**. The losers are those buyers, who pay a
month-turn price about 0.9pp above the mid-month trough relative to HYG. The mid-month leg includes the known
post-ex drift (EVENTS trial 3). The z-score cannot see either leg: the 252-session window treats the monthly
cycle as noise, and the dollar-neutral book holds almost no net CEF exposure at the month turn (net weight +0.02).

**The screen, with the controls named before each run:**

| check | result |
|---|---|
| Discount leg, k−3..+3, credit 17 (excess over days ≥ 6 sessions from a month-end) | cumulative **+74.8bp**; k 0, +1, +2 at t 3.36, 3.56, 2.91 |
| Same, C4's 74 | +41.9bp by k+1 (t 3.71 and 3.13 at k 0 and +1) |
| **Control: iShares ETF premium change** (HYG LQD IEF TLT SHY; AP arbitrage) | flat: −0.14bp by k+1 |
| **Control: equity and HY beta** (leg residualised on same-day SPY and HYG) | still **+51.2bp** by k+2 (t 3.46, 2.97, 2.06) |
| Price leg vs NAV leg, credit 17 (raw, so both carry the market) | quarter-end day: price +25.5bp (t 4.13), NAV +4.0bp (t 1.12); other month-ends: price +12.6bp (t 2.69), NAV +6.4bp (t 3.08). Price carries it |
| **Control: the fund's own DRIP agent** (buys only at a discount; agenda B3's control) | **fails**: discount name-days +55.9bp, premium name-days +54.0bp over k−2..+2. Not the plan agent |
| Ex-date contamination | removed: no ex-date from k−8 to k+2 gives +50.8bp (t 5.44) |
| By sponsor (k−2..+2 leg) | AB +27, BlackRock +27, DoubleLine +88, Nuveen +28, PIMCO +45bp |

**The tradable form.** It is a pre-scheduled MOC calendar trade that needs no NAV and no CEF borrow. Buy the CEFs
at the close of k−3, sell at the close of k+2, short HYG (easy to borrow at Alpaca on 2026-10-12/15 [S:
`docs/REFERENCES.md` rows of those dates]) over the same sessions. Total returns, all name-days:

| source | months | minus HYG, bp/month | t | eras 05-09 / 10-14 / 15-19 / 20-22 | placebo (10 sessions earlier) |
|---|---:|---:|---:|---|---|
| repo panel, credit 17 | 187 | +48.7 | 5.13 | 66 / 23 / 42 / 87 | −43.3 (t −3.72) |
| **CRSP `ret`, deployed 13** (second source) | 187 | **+54.6** | **5.06** | 75 / 29 / 46 / 94 | −42.4 (t −3.28) |
| CRSP, munis vs MUB, rest vs HYG | 182 | +59.0 | 2.96 | — | — |

- **Robustness (CRSP):** median +57.4bp; 5%-trimmed mean +56.7bp (t 8.87); +55.8bp without 2008–09 and 2020 H1.
- **Rates beta:** IEF's window return carries β +0.49 (the X3 month-end Treasury effect is in there). The
  intercept is +45.6bp.
- **Fit-book correlation:** monthly +0.105.

**Costs.** One unit of notional turns 4 units a month: in and out, on both legs.

- On the desk's uniform grid the net is +34.6 / **−5.4** / −65.4bp a month at 5 / 15 / 30bp. **It flips sign
  by 15bp: a D2 risk.**
- A labelled sensitivity charges HYG 1bp a side [U: assumed]: +42.6 / +22.6 / −7.4bp.
- Paper's measured late-market cost is 5.1bp a side; the real-money MOC cost is unmeasured.

**Expected gross gain on all capital** (model, from the fit, post hoc):

| case | gross, % of capital a year | vol |
|---|---:|---:|
| fit effect, sleeve at 0.5× capital, 5 of about 21 sessions a month | +3.3 | about 2.5% |
| planning case: half the fit effect | +1.6 | about 2.5% |

**Paper artefact in this sleeve.** HYG went ex at k+1 in 92% of months (2015–22), a mean of 42.1bp. Alpaca paper
books no payment in lieu, so a paper short over k+1 books that drop as a gain. **The sleeve must be scored on
total return**, or hedged with an instrument that does not go ex inside the window. The CEF leg has no ex-date in
the window.

**Graveyard check.**
- It is not the stale-price well: the tradable form uses closing prices and total returns only.
- It is not `leadlag`: the prices are executable closes.
- It is not X3: the TERM part is measured, and the intercept survives it.
- The two patterns that killed earlier ideas are tested here. The ETF control is flat and the placebo has the
  opposite sign.
- It is related to, but not the same as, agenda **B3** (DRIP buying on payable dates; EVENTS, never run). B3's
  premium/discount control fails here, so B3 as written would be killed by its own control while the effect
  stays.

**Cheapest test that could kill it** (zero returns read; needs the team lead's credentialed R2 pull of
`crsp_a_stock.dsedist.paydt` for the 17 over 2005–22). Re-anchor the discount leg on each fund's actual pay date.
The pressure should move with pay-date conventions: BIT, HYT and DSL pay on the last business day; PIMCO and
Nuveen on the 1st; AWF mid-month.
- **If it stays pinned to the calendar month-end regardless of pay date, the pay-date mechanism is dead.** The
  calendar effect would then still need its own mechanism before any trial.

**Power.** Normal approximation, at the fit's mean and sd (147bp a month); `angle_turn_of_month.py` section 8:

| test set | effect | P(t ≥ 2.039), EVENTS at declared N = 8 | P(t ≥ 2.825), CEF at N = 54 |
|---|---|---:|---:|
| 2023-01 → 2026-09, the 13/17 (45 months) | fit | 0.67 | 0.37 |
| same | half | 0.21 | 0.06 |
| the 27 untouched names, 2007–22 (sd assumed equal) | fit | 0.999 | 0.99 |
| same | half | 0.69 | 0.39 |

- **The cross-sectional set is the powerful test.** It is still sealed: E1 consumes it at its Stage 1, which has
  not run [S: `docs/RESEARCH_STATE.md` ACTIVE row at `862b1d0`]. Using it for F would consume it, which is the
  team lead's call.
- The core's 2023+ has been seen in aggregate (Q7 of trial 53). This statistic has not been computed on it.

**What would make it uninteresting:**
- the pay-date test pins the effect to the calendar;
- the 27-name set shows it at under half the fit effect;
- or measured real-money cost exceeds about 12bp a side on the CEF leg.

---

## A. The live NAV drag is noise in a decomposition, not a cost (KILL)

`angle_nav_leg.py`; output `angle_nav_leg_output.txt`.

**Question.** The live attribution: NAV part −2,250.74, discount part +1,583.47, hold −667.27 over 09-29..10-30,
muni NAV part −1,849.36 [V, `results/cef/LIVE_ATTRIBUTION_2026-11-02.md`]. Is the drag predictable from a NAV-lag
measure known at t, and can the book stop paying it?

**Mechanism tested.** Under stale NAVs, the NAV part and the discount part trade P&L between them, and the hold
does not move. If the drag were predictable from the lag at t while the hold was not, it would be an identity,
not a loss. **Negative control:** the same forecast must not predict the price-based hold. An ETF hedge's
component must have a mean near zero, or it is a factor bet (D4).

**Fit, unit book.** Active days run 2013-06-25 → 2022-12-30 (pre-2013 is flat for the 13 names: landmine 8);
% of capital a year:

| era | NAV part (t) | discount part (t) | hold, SR | vol: NAV / disc / hold | corr(NAV, disc) daily / 25-day | 25-day windows with NAV < 0 and disc > 0 |
|---|---|---|---|---|---|---:|
| 2010–14 (from 2013-06) | −0.31 (−0.13) | +9.95 (2.06) | +9.64, 1.63 | 3.4 / 6.2 / 5.9 | −0.35 / −0.19 | 37.5% |
| 2015–19 | −0.41 (−0.44) | +5.45 (1.82) | +5.04, 0.72 | 2.2 / 7.0 / 7.0 | −0.15 / +0.07 | 33.3% |
| 2020–22 | −0.02 (−0.01) | +7.12 (2.18) | +7.10, 1.08 | 2.3 / 6.8 / 6.6 | −0.29 / −0.45 | 32.3% |
| **fit** | **−0.27 (−0.36)** | **+6.70 (3.29)** | +6.43, 0.96 | 2.5 / 6.8 / 6.7 | −0.23 / −0.20 | **37.5%** |

**Findings.**
- **The edge is the discount part.** The NAV part is unpriced and carries about 14% of the hold's variance.
- **The live five weeks are ordinary.** A negative NAV part beside a positive discount part occurs in 37.5% of
  fit 25-session windows.
- **The NAV lag does not predict it.** Two forecasts were built from data at t:
  - a trailing-252 regression of the NAV on its own price two to four sessions back: slope −0.004 (t −0.03) on
    the NAV part, and t 0.01 on the hold control;
  - the NAV's own lags: t 0.43 on the NAV part, t 1.19 on the hold.

  The forecast has 25% of the NAV part's sd, so a real pass-through (slope 1) would have shown; slopes near 1 are
  excluded.
- **The ETF hedge makes it worse.** MUB, HYG, IEF and LQD, plus BKLN from 2012, Dimson lags 0–2:
  - in-sample R² is 2.1–2.7% for the hold and 3.2–5.1% for the NAV part;
  - out of sample (betas strictly before each day) variance **rises** by 20–49%;
  - a position-based hedge (per-name trailing betas × held weight) also raises it, by 9–14%.

  No hedged Sharpe is reported, because comparing variants is a trial.

**Graveyard.** `single-fund-PD` and W4's stale-part test have the same shape: staleness reallocates and does not
earn. This closes the live version of the question.

**Verdict.** **KILL.** There is nothing to stop paying: the drag is neither predictable nor hedgeable with these
instruments. The live loss is the hold's −667, which is noise at five weeks.
- **What would reopen it:** a hedge instrument that tracks the book's group NAV spread (muni against taxable)
  far better than MUB−HYG does here.

---

## B. Paper-scoring mechanics (PAPER ARTEFACT, not alpha)

`angle_paper_scoring.py`; output `angle_paper_scoring_output.txt`. The fill figures are the 2026-11-02
fill-drift measurement: 344 fills, aggregates only [V there; read, not re-fetched]. Its `aggregates.json` sits in
the session scratchpad, outside the repository, and the script reads it from there.

**(1) Distributions.** Paper credits a long nothing and charges a short nothing. Fit, unit book, % of capital a
year:

| era | leg the paper record omits (t) | long credited | short charged | gross SR, price / total |
|---|---|---:|---:|---|
| 2010–14 (from 2013-06) | −2.31 (−1.74) | +5.60 | −7.91 | 1.63 / 1.30 |
| 2015–19 | +0.67 (1.95) | +6.52 | −5.85 | 0.72 / 0.84 |
| 2020–22 | −0.61 (−1.47) | +4.82 | −5.43 | 1.08 / 1.02 |
| **fit** | **−0.21 (−0.65)** | +5.84 | −6.05 | **0.96 / 0.96** |

- **The book is not structurally long or short yield** (the negative control holds). This matches the harness
  docstring's −0.01%/yr for 2005–26 [S].
- The live +0.32% of capital over 24 sessions sits at the **94th percentile** of fit 24-session sums (median
  0.00%, 5–95% range −0.49% to +0.35%). This book is unusually long yield right now. The sign is not fixed: C4's
  fit was the other way (price-only 1.360 against total 1.217 [S, r3]).
- **No construction-neutral fix.** Only the trade filled at the close before an ex-date could be deferred, and it
  carries 7.2% of the leg. Its fit mean is −0.30%/yr (net short-yield), so deferring would **lower** the paper
  score.
- **The fix is scoring:** judge paper on the total-return line that `quantt/session/dist_score.py` already
  computes, beside the official-close line.

**(2) Late-market fills** (paper only; rule 3's recorded exception).

- **The cost is the half-spread, not drift.** Against the close, B = 5.1bp ≈ E 6.2bp (the half-spread paid at the
  fill) − 1.1bp (the move from the fill to the close in our direction, C − D).
  - This is the ordinary quoted spread. CRSP's closing half-spread on the 13 names, 2020–22, has median 7.65bp
    (hy 5.0, loan 6.3, multi 7.9, muni 9.4; n 9,556).
  - A marketable order pays it, and it is known before the order.
- **Not predictable:** the pre-15:50 move × side has t 0.55 (17 days) [V there].
- **Buys cost more than sells** (A 15.0 vs 6.6bp). The mid's drift 15:50 → fill is 8.6bp for buys and 0.7bp for
  sells: 65 symbol-days, untested. A real-money MOC fill pays neither.
- **Size:** at the fit's turnover ×1.13 it is 0.45%/yr (2015–19, 7.8 turns a year) to 1.24%/yr (2020–22, 21.5
  turns a year) of capital on paper.

**Aside, for whoever owns the runner.** The live account traded $570,482 in 20 sessions on about $100,000: 5.7× capital.
- The fit's 20-session windows have median 0.01×, 95th percentile 4.42× and 99th 6.29×.
- Even allowing for the build from flat on 09-29, live turnover is at the top of the fit's range.
- This is not this note's question, but paper costs scale with it.

**Verdict.** **PAPER ARTEFACT on both counts.** Neither is real-money alpha and neither warrants a trading
change. Score paper on total return and on the official close.

---

## C. Record-date borrow recall in muni CEFs (KILL as a cost)

`angle_muni_recall.py`; output `angle_muni_recall_output.txt`.

**Mechanism.** A payment in lieu of a muni-CEF distribution is ordinary income to the lender, never exempt
interest (`docs/REFERENCES.md` "Payment in lieu" rows [V]/[S]). Taxable lenders therefore have a monthly reason
to recall before each record date. A fixed share count cannot grow the lendable pool, so fees should rise into
the record date.
- **Who loses:** our muni shorts (MHD, MQY), in real money only. Paper charges no borrow.
- **Control** (named first): taxable credit CEFs, whose distributions are ordinary income either way, plus a
  placebo event 10 sessions earlier.

**Data.** `data/cef/cef_borrow_history.parquet` (IBKR FEE_RATE, 44 names, 2021-09-13 → 2026-09-09; levels [S]
before 2026-09) × ex-dates (`cef_distributions.parquet`, last 2026-09-10). Fees are costs, not returns: the fit is
the headline, and the later windows are cost data.

| window | muni, log fee k−3..0 (t) | taxable (t) | muni placebo (t) |
|---|---|---|---|
| **fit, 2021-09 → 2022-12** | **+0.003 (0.08)** | +0.003 (0.04) | −0.149 (−2.24) |
| 2023-01 → 2024-05-27 (T+2) | +0.055 (3.10) | −0.050 (−1.46) | −0.019 (0.20) |
| 2024-05-28 → (T+1) | −0.015 (−0.89) | −0.020 (−0.39) | −0.046 (−1.63) |

**Findings.**
- The predicted shape shows only in 2023–24, and is gone under T+1.
- Even there, +5.6% of a median base fee of 7.9%/yr for about four sessions a month is about **0.08%/yr of muni
  short notional**.
- The real cost is the base level, not the hump. Muni median base fees were 17.7%/yr in the fit window, 7.9% in
  2023–24 and 5.8% since T+1 [S levels].

**Verdict.** **KILL.** It closes catalogue row E3 at zero trials.
- **What would reopen it:** a share-availability series (not fees) that shows recalls the fee does not price.

---

## E. Bond-holiday stale NAVs: the band barely trades them (KILL, closes CA9)

`angle_bond_holiday.py`; output `angle_bond_holiday_output.txt`.

**Mechanism.** On Columbus Day and Veterans Day the NAV carries bond prices while the shares trade. The book is
the loser if the band trades the artefact.

**Why it is still live.** CEFConnect will confirm 2026-11-11's repeats, so the live gate
(`quantt/session/nav_gate.py`) classes them as genuine and keeps them.

**What was already known** (W4 §3e [S]): NAVs unchanged on 42% of holiday name-days.

**Kill test.** This is the catalogue's own unrun test, with ±5 sessions as the control.

| decisions | dates | with trades | turnover | 5-session P&L per unit turnover | total |
|---|---:|---:|---:|---:|---:|
| bond holidays | 19 | 5 | 0.225 | −20.0bp | −0.045% of capital |
| control, ±5 sessions | 38 | 11 | 1.691 | −3.9bp | −0.066% |
| all active dates | 2,394 | 1,078 | 128.6 | +18.0bp | +23.1% |

**Findings.** Bond-holiday decisions carry **0.17% of fit turnover** (0.79% of dates). Saturday Veterans Days are
treated as no holiday [U: SIFMA's Saturday practice was not fetched].

**Verdict.** **KILL.** Nothing to do for 2026-11-11.

---

## D. Leverage-cost pass-through (KILL; MACRO untouched)

`angle_leverage_cost.py`; output `angle_leverage_cost_output.txt`.

**Mechanism.** Short rates up → leverage cost up → net investment income down → distribution cut → wider
discounts in levered fixed-rate funds. That is a level shift the z-score reads as cheap.
- **Control:** floating-rate loan funds (JFR), whose income resets with the same rate.
- **Duration** is controlled by IEF's same-month return.

**Data.** Discounts are the harness panel for the 17 (no sealed name). The short rate is
`data/financing_curve.parquet` `base_rate_pct` (DFF, last 2026-07-20).

**Monthly results, 2005–22.** Next-month discount change per pp of 3-month rate change:

| comparison | slope (t) | with IEF (t) |
|---|---|---|
| muni − loan | +0.61 (1.20) | +0.68 (1.42) |
| taxable fixed-rate − loan | −0.17 (−0.26) | −0.14 (−0.18) |
| muni alone | −0.18 (−0.68) | — |
| loan alone | −0.80 (−1.48) | — |

**Findings.**
- The 3-month horizon gives +0.57 (t 0.64) and −0.77 (t −0.51).
- There are 12 runs of ≥ 50bp moves in 18 years.
- The predicted sign fails, and the episode count is D7 for any later trial.

**Verdict.** **KILL.** It joins r1's SIFMA-state null.

---

## Not screened (labelled speculation)

- **Sponsor and family effects.**
  - F's pressure is common to all five sponsors in the 17.
  - Board actions, family mergers and tenders are E1, A1 and alpha-finder territory.
  - Fee changes: no local data.
- **Rule 2a-5 (compliance 2022-09-08)** can change a family's NAV smoothing without announcement, just before the
  time holdout. That is a dated break a rolling z reads as signal. It is untestable on the fit (four months);
  measure NAV autocorrelation by family when 2023+ NAVs are next read for any reason.
- **§18(a) coverage deleveraging** fires in 2008 and 2020 only (D7), and the leverage data start with N-PORT in
  2019.
- **Reg SHO threshold buy-ins:** there is no threshold-list data locally.

## Reproduce

From the worktree root (`862b1d0` plus this folder). The ETF and CRSP inputs are gitignored caches in sibling
worktrees, named in each script's docstring:
- `trial-xasset/.../etf_daily_xasset.parquet`;
- `research-prereg-c5/.../crsp_dsf_w4.parquet`;
- `exdrift-stage0/.../crsp_dsedist_2023_2024.parquet`, which was read for pay-date conventions only.

```bash
python3 -B results/cef/screens_2026-11-02/angle_nav_leg.py
python3 -B results/cef/screens_2026-11-02/angle_paper_scoring.py
python3 -B results/cef/screens_2026-11-02/angle_muni_recall.py
python3 -B results/cef/screens_2026-11-02/angle_bond_holiday.py
python3 -B results/cef/screens_2026-11-02/angle_leverage_cost.py
python3 -B results/cef/screens_2026-11-02/angle_quarter_end.py
python3 -B results/cef/screens_2026-11-02/angle_turn_of_month.py
```

Panels, with their last dates and the cut used:

| panel | last date | cut |
|---|---|---|
| `data/cef/cef_prices.parquet` / `cef_nav.parquet` | 2026-10-15 / 2026-10-14 | 2022-12-30 |
| `cef_distributions.parquet` | last ex-date 2026-09-10 | 2022-12-30 |
| `data/cef_families/*` | 2026-10-09 | 2022-12-30 |
| `data/etf_daily.parquet` | 2026-10-09 | 2022-12-30 |
| `data/holdings/ishares_nav_daily.parquet` | 2026-09-18 | 2022-12-30 |
| `data/financing_curve.parquet` | 2026-07-20 | 2022-12-30 |
| `cef_borrow_history.parquet` | 2026-09-09 | fees, not returns: fit headline, later windows labelled cost data |
| CRSP W4 cache | 2004-01-02 → 2022-12-30 | — |
