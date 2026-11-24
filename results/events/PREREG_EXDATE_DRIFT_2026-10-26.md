# Pre-registration — the post-ex-date drift in credit CEFs: (a) defer the band's buys around ex-dates; (b) short at the ex-date close, cover at +3, peer-hedged

**Date** 2026-10-26 (drafted; inputs computed 2026-10-27) · **Counters** two trials proposed
(decision 1): **(b) EVENTS**, trial 3 if approved first, judged at the N of decision 4
(recommended N = 7); **(a) CEF**, trial 53 at N = 53 (decision 2), or withdrawn on power
before any data step (decision 3, recommended) · **Pass bar** `scripts/cef/validate.py::_dsr`
> 0.95 **on the clean test set**, never on the fit · **Evidence** `results/cef/screens_2026-10-26/`
on `simon` at `7c02236` · **Author** research agent, for the team lead

> **APPROVED by the team lead, 2026-10-27, with every recommended answer in §14.**
> - Part (b) is EVENTS trial 3, judged at N = 7. The counter moved 2 → 3 in the commit that records this.
> - Part (a) is withdrawn on power before any data step: no trial, and CEF stays 52.
> - Stage 0 (§8) runs before any 2023+ return.
>
> *Was:* DRAFT, awaiting team-lead approval (2026-10-26).
>
> **AMENDMENT 1 WITHDRAWN (team lead, 2026-10-28), before any test return. The opening runs the ORIGINAL
> pre-registered design, with no MUB/IEF hedge leg.** The reasons:
> - on the full 2005–22 fit, the original design passes D4: alpha t 4.57, MUNI −0.07, TERM −0.03
>   (`results/events/exdrift/exdrift_fit_d4_full_window.csv`, committed at `4bab4cf`, conclusion at
>   `533b131`);
> - amendment 1 lowers the deflated Sharpe to 0.93 (NEITHER), and makes the cap bind on 18.5% of rows;
> - it was prompted by the 2021–22 rehearsal alone.
>
> **Known risk, stated plainly:** every 3.8-year fit era failed D4 on its own. 2005–09 failed on
> alpha; 2010–15 and 2021–22 on MUNI and TERM; 2016–20 on HY +0.21. The test window is about that long
> (2023-01-03 → 2026-10-09, 946 sessions).
>
> The amendment's text and both of its rehearsals stay in the record below. The rehearsals are
> `exdrift_rehearsal_fit_2021_22_amendment1_WITHDRAWN.json` and the first derivation's figures in the
> text. The original design's rehearsal is `exdrift_rehearsal_fit_2021_22.json`.
>
> *Withdrawn text follows.*
>
> **AMENDMENT 1 (team lead, 2026-10-28), recorded BEFORE any test return.** The 2023+ set is unseen.
>
> **Provenance, stated plainly.** The amendment was prompted by a result on FIT data:
> - The fit-only rehearsal of the opening's code (2021-01-01 → 2022-12-30,
>   `results/events/exdrift/exdrift_rehearsal_fit_2021_22.json` at commit `8b08761`) failed stage 5.
> - Its alpha t was 2.90 against 3.0, and its summed betas at the vol target were MUNI −0.41 and
>   TERM −0.39.
> - It is a design change chosen after seeing a fit statistic. The test set is untouched, and the
>   judging is unchanged: N = 7, gross deciding, the grid and borrow beside. EVENTS stays 3.
>
> **The amendment.** Part (b) hedges each event's muni and Treasury-duration exposure with MUB and
> IEF, at betas estimated on the FIT window only, frozen here, and never re-estimated on test data.
> - **The betas** come from one OLS per fund on 2007-09-11 → 2022-12-30 (MUB's first return to the
>   fit's end). The fund's r6 total return is regressed on stage 5's own nine factors (French six;
>   TERM = IEF − RF; HY = HYG − IEF; MUNI = MUB − IEF), each at t and t−1, lags summed.
> - The hedge exists to remove what stage 5 measures, so its betas are stage 5's partial betas.
>   They are derived, not swept. They are frozen in `results/events/exdrift/exdrift_amendment1_hedge_betas.json`:
>
> | fund | AWF | BIT | DSL | HYT | JFR | MHD | MQY | PCN | PDI | PDO | PFN | PHK | PTY | NAD | NEA | NVG | NZF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| β MUNI | +0.138 | +0.447 | -0.046 | +0.312 | +0.550 | +1.085 | +1.089 | +0.881 | +0.774 | +0.920 | +0.294 | +0.384 | +0.412 | +0.982 | +1.075 | +0.970 | +1.085 |
| β TERM | +1.105 | +1.236 | +1.102 | +1.152 | +0.982 | +1.692 | +1.569 | +1.759 | +1.480 | +1.475 | +1.377 | +1.738 | +1.601 | +1.512 | +1.436 | +1.614 | +1.729 |
>
> - **Per event** (a $1 short of fund i and a $1 equal-weight long of its H-E basket B):
>   - the exposure is E_f = −β_i,f + mean of β_B,f, for f = MUNI and TERM;
>   - the hedge holds h_MUB = −E_MUNI of MUB and h_IEF = E_MUNI − E_TERM of IEF. Because
>     MUB = MUNI + IEF and IEF = TERM + RF, this offsets both exposures and leaves HY untouched;
>   - the hedge is held on the event's decision rows e−1..e+1, so it earns rows e+1..e+3. It is
>     netted across events, scaled by k with the rest of the book, and capped with it;
>   - long MUB where the event is net short muni; the IEF leg follows from the formula.
> - **Which stages see the hedge.** Stages 1, 2, 4, 5 and 6 use hedged P&L. Stage 3 compares the
>   unhedged NAV leg with the unhedged price leg on the same events (O3). The hedge is a price
>   overlay, and the same ETF P&L would otherwise enter both legs.
>
> **Gross cost against the 1.80 cap**, on the fit rehearsal:
> - per event unit, the hedge's gross is 0.59 on average (at most 1.15). The mean h_MUB is +0.096
>   (long in 56% of events) and the mean h_IEF is −0.089 (long in 38%);
> - the sized book's largest gross rises from 1.76 (CEF legs alone) to 2.44;
> - **so the cap now binds, on 62 of 149 decision rows (41.6%), where it bound on none before.**
>
> **Disclosed, against ourselves.**
> - A first derivation regressed each fund on MUB and IEF total returns alone. It omits the factors
>   stage 5 controls for, HY above all, so its MUB beta absorbed credit exposure (+1.0 to +2.4 for
>   every fund).
> - Rehearsed on the fit, that derivation gave MUNI −0.41, TERM −0.32 and alpha t 3.08, with the cap
>   binding on 22% of rows. It was replaced on that argument, and both are reported.
> - Both rehearsals are IN-SAMPLE for the hedge ratios, because the estimation window contains
>   2021–22.
>
> **The re-rehearsal with the amendment** (fit 2021–22 only, the same code and window as before):
>
> | stage | result | rule |
> |---|---|---|
> | 1 | 375 events, +23.9bp per event, month t 2.79 | PASS |
> | 2 | pooled placebo +3.6bp | PASS |
> | 3 | NAV leg +4.5bp against price +23.9bp | PASS |
> | 4 | 13 names: +19.8bp, t 3.76 | PASS |
> | 5 | alpha t 2.59; at target MUNI −0.37 (HAC se 0.15), TERM −0.39 (se 0.15) | **FAIL** |
> | 6 | `_dsr` 0.96 | PASS |
>
> - **Amendment 1 as derived does not cure the fit rehearsal's D4 failure.** Static per-fund betas
>   do not reproduce the sleeve's 2021–22 MUNI and TERM exposure, which is about 2.5 standard errors
>   from zero.
> - *(Superseded: the team lead WITHDREW amendment 1 on 2026-10-28; see the block above it.)*
>
> **What was computed to write this.** Five helpers in this folder, run 2026-10-27:
> `prereg_inputs.py`, `prereg_inputs_b2.py`, `prereg_inputs_b3.py`, `prereg_power_he.py` and
> `prereg_placebo_counts.py`. Their outputs are `*_output.txt` and `*.json` beside them.
> - **Fit window, 2005-01-01 → 2022-12-30.** They read prices, NAVs, distributions and HYG
>   returns through parquet filters at 2022-12-30, so no later row was loaded. Every frame is
>   asserted to end there. Everything they computed on these rows is **descriptive and post-hoc**
>   (§0.1).
> - **2023-01-01 onward: dates only.** They read the `ticker, ex_date` columns of the
>   distribution panel and the `date, ticker` columns of the price panel, to count events,
>   sessions, months and basket sizes. **No 2023+ price, NAV, distribution amount, return or
>   fee was read.**
> - **The 27 sealed names** (`data/cef/cef_universe.csv` minus the 17) were never loaded.
>
> **Labels.** [V] = computed now by those helpers. [doc] = copied from a repo note, named.
> [S] = sourced, not re-read today. [U] = uncertain, or arithmetic on stated assumptions.

---

## 0. The declaration in one table

| item | (a) execution-timing overlay | (b) standalone sleeve |
|---|---|---|
| what is tested | The live policy (`band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)` on the spec's 13) **may not raise a fund's signed weight** on a decision session from 2 before to 1 after any of its declared ex-dates (offsets −2..+1). The band resumes, against that day's target, at decision e+2 (§3) | **Short each eligible fund at the close of its ex-date e, cover at the close of e+3**, against a long equal-weight basket of peers (H-E, §4.3). Decide at the close of e−1, fill at the close of e, earn rows e+1..e+3. Shift(2) exactly |
| universe | the spec's 13 (`spec.UNIVERSE`) | test: the 17 credit CEFs (the 13 + NAD, NEA, NVG, NZF). Live: names `shortable` at Alpaca at the decide |
| score | the daily P&L difference D = pnl(overlay) − pnl(unmodified), **gross, total-return basis**, at turnover matched within 5% (H2) | the per-event mean gross P&L (month-clustered t), and the tradable sleeve's daily gross P&L |
| harness | `band_gross_capped(..., defer_up=None)`, a default-off flag added visibly, with the no-op proved byte for byte (§3.4) | `event_hold` (unchanged; its `ann` is the declaration date) → `evaluate` → `_cap_gross`; `borrow_charge` in its own column (§4.5) |
| clean test set | the 13, 2023-01-01 → the last panel date. Their book-level 2023+ P&L has been seen; the overlay's difference has not (§5.2) | **the 17, 2023-01-01 → the last panel date (the team lead's ruling, decision 5).** Today: 752 events, 714 with a basket, on 169 dates in 45 months [V, dates only] |
| fit 2005–22 | **descriptive only**: the effect was found after the fit was seen (§0.1) | same |
| named controls | placebo calendar +5 / −10 (§3.6); NAV leg; z-blind replication (report-only) | placebo calendar +5 / −10 (§4.6); NAV leg |
| kills | D1 (t < 2), either control ≥ ½ the effect, D4, the bar (§9.2) | D1, either control ≥ ½, the 13-name sign (D6), D4, the bar (§9.1) |
| headline / costs | gross; the 5 / 15 / 30bp grid beside it, labelled, deciding nothing (E1 amendment 1: "ignore fees, just look at PnL") | same; borrow in its own labelled column, deciding nothing |
| power on the clean set | **inadequate.** First-order expected t 0.80; P(t ≥ 2) ≈ 0.11; P(bar) ≈ 0.000–0.003 [U on V inputs] (§10) | per event: P(t ≥ 2) 0.94 at the fit effect, **0.41 at half of it**. The bar: about 0.46 at the fit effect, 0.03 at half [U on V inputs] (§10) |
| what changes if it passes | (a): a frozen-spec key, absent = off, through `/spec-change`. (b): its own sleeve spec, default off, inside the CEF account. **This trial writes neither.** Revert: delete the key | (same row) |

### 0.1 Provenance: the fit is spent, and what was seen when

**The effect was found after the fit window had been looked at, more than once.** Every fit
figure below is therefore a description, never evidence. The decision rests on the clean
test set alone (§5).

| date | where | what was seen | label |
|---|---|---|---|
| 2026-10-08 | `results/cef/RESEARCH_AGENDA_2026-10-08.md` l. 402 | "Ex-day dividend capture" closed, because "paper credits no dividends, so the result cannot be measured on the scored account" | [doc] |
| **2026-10-11** | `results/cef/W4_ARTIFACTS_2026-10-11.md` §1; `docs/BRIEF.md` §3 | **First measurement, on the deployed 13, 2005–22.** The discount falls 0.167pp on the ex-date and "keeps falling for two sessions"; "a post-ex-date price pattern, not arithmetic" | [doc] |
| 2026-10-12 | `results/cef/CORE_SIGNAL_CANDIDATES_2026-10-12.md` §3 | The deployed 13's same-day abnormal total return: −1 **+12.65bp** (NW t 2.30), +2 **−11.49** (−2.24), +3 **−8.61** (−2.40). The "(a′) freeze" is proposed (CEF, one trial, never run). The standalone trade is called "D2 here: about 24bp abnormal against two crossings of a 32.6bp breakeven" | [doc] |
| 2026-10-26 | `results/cef/screens_2026-10-26/r3_c4_exdate/NOTE.md` | C4's ex-window concentration called REAL on C4's 74 family funds. The price falls 1.03× the distribution; NAV β0 1.032; the price slope continues at β+1 +0.137 and β+2 +0.074 while NAV does not | [doc] |
| 2026-10-26 | `results/cef/screens_2026-10-26/r3_review/` (scripts `a1.py`–`a7.py`, no saved output); its verdict is in `results/cef/screens_2026-10-26/README.md` | **MIXED.** "The post-ex drift is real and generic, and shorting into any ex-date earns it. Once that profile is removed, the C4-specific window excess is t 1.69 against the 2.0 bar" | [doc] |
| 2026-10-26 | `results/cef/screens_2026-10-26/r6_exdrift/NOTE.md`, `out.txt`, `out_credit.txt` | Short at the ex-date close, cover at +3. CAR(+1..+3) −34.3bp (t −14.9) on C4's families over 2005–22 (−30.1bp, t −5.6, over 1982–2022; *corrected 2026-10-27*), and **−20.5bp (t −6.8) on the 17 credit CEFs, 2005–22** | [doc]; the 17's figure is reproduced exactly by this draft's gate [V] |
| 2026-10-27 | this folder | The 17's profile at −5..+6 by group; r6's statistic by era and by group; three hedge candidates (calendar feasibility and dispersion); the NAV leg; the deployed band's buys in the window | [V], all fit-only |

**Two corrections to the brief this draft was written from:**
- **The drift was not first seen by the reviewer.** W4 measured it on the deployed 13 on
  2026-10-11. The reviewer re-found it as a generic effect on 2026-10-26.
- **r6's −30.1bp on C4's families is not a 2005–22 figure.** `out.txt` prints the event span
  "first 1982-02-10 last 2022-12-22": it covers every year in the families panel. Its 2005–22
  splits, Eaton Vance excluded, are −33.0 / −30.5 / −38.1bp for 2005–09 / 2010–15 / 2016–22
  [doc]. **The credit figure is 2005–22** (`check_credit.py` filters `date >= 2005-01-01`).

---

## 1. What is tested, and what changes

- **(a)** asks whether the live band loses P&L by buying into the post-ex drift, and whether
  deferring those buys is worth it to the deployed book at matched turnover.
- **(b)** asks whether the drift is a standalone, hedged, tradable gross P&L source that is
  alpha rather than beta.
- **Both rest on one mechanism** (§2), but they are two decision rules on two different P&L
  series. So they are **two trials** (decision 1).
- **If (a) passed:** a frozen-spec key, absent = off. It needs:
  - the byte-for-byte no-op diff of sleeve output with the key absent (`/spec-change`);
  - the declared ex-date calendar at decide time (a live dependency, §7);
  - a test that fails against today's behaviour.

  The one-line revert is to delete the key.
- **If (b) passed:** its own sleeve spec, default off, inside the CEF account (the 2026-10-09
  "one combined book" ruling). It also needs a paper H11 statistic (§11), a release and a
  team-lead go.
- **This trial writes no key and touches nothing on the order path.**

The full "not tested" list is §13.

## 2. Why, mechanically, who is on the other side, and the graveyard

### 2.1 The mechanism

- **To receive a distribution, a buyer must own the fund at the close of e−1, the last
  cum-distribution session.** That holds in every settlement regime (§4.2).
- **Our reading [U as a mechanism]:** income-seeking and dividend-capture buyers lift the price
  into e−1 and sell after e.
- **What the fit shows (17 names, abnormal total return against the same-date equal-weight
  mean, bp, se about 1.4) [V]:**

  | offset | −5 | −4 | −3 | −2 | −1 | 0 | +1 | +2 | +3 | +4 | +5 | +6 |
  |---|---|---|---|---|---|---|---|---|---|---|---|---|
  | **17** (3,226 events) | +2.6 | +4.2 | +5.1 | +5.1 | **+11.1** | −3.2 | **−10.1** | −4.8 | −5.6 | +1.5 | −1.9 | +0.2 |
  | **deployed 13** (2,352) | +5.4 | +5.3 | +6.4 | +6.7 | +9.1 | −3.9 | **−11.4** | −7.4 | −6.5 | −1.2 | −0.7 | +1.0 |
  | **4 Nuveen munis** (874) | −4.9 | +1.4 | +1.7 | +0.9 | +16.6 | −1.2 | −6.5 | +2.2 | −3.2 | +8.9 | −5.1 | −2.1 |

  The price drops by more than the cash on e, falls for three more sessions, then stops.
- **NAV does not move.** On the fit's strict-basket events the NAV leg (§4.6) is **−0.63bp
  (t −0.29)** [V]. On C4's 74 funds NAV β0 is 1.032 with |β±1| ≤ 0.026 [doc r3].
- **So this is a price-flow effect, not a NAV or mark effect.** That is the property the NAV
  control tests (§9).

### 2.2 Who is on the other side, and why they stay

- **Yield-chasing and dividend-capture holders [U].** They buy before the record date for the
  cash and sell after. For monthly payers this is a standing, calendar-driven flow
  (`CORE_SIGNAL_CANDIDATES` §3, [doc]).
- **Why it is not arbitraged away, stated against ourselves:**
  - A liquidity provider pays four spread crossings on a three-session round trip (§6).
  - The short side of thin CEFs is scarce, and muni lenders recall before record dates
    (`docs/BRIEF.md` §3, [doc]).
  - **If those costs are the reason, the gross effect is the price of liquidity**, and net of
    it may be nil. The grid is shown beside the verdict for that reason. It decides nothing,
    by the paper-scoring ruling.
- **The fit concentrates in taxable funds [V, descriptive].** Taxable 11: +29.3bp per event
  (month t 5.23). Muni 6: +7.5bp (t 1.17). This was seen before writing, so the headline set
  is the pre-specified 17, not the taxable subset (decision 6).

### 2.3 The graveyard (`docs/RESEARCH_STATE.md`; the agenda's closed list)

| relative | how this differs, and the risk that remains |
|---|---|
| **"Ex-day dividend capture"** (agenda 2026-10-08, closed: paper credits no dividends) | **(b) neither owes nor receives a distribution, by construction.** The short opens after the record cut-off (§4.2), and no basket fund holds over its own ex-date (§4.3). So price-only equals total return on every held cell, and paper can score it. (a) changes which distributions a long receives, so it is decided on total returns, with the third P&L line on paper. **The real-money verdict is D2** (§6) |
| **(a′) ex-cycle freeze** (`CORE_SIGNAL_CANDIDATES` rank 3, proposed 2026-10-12, never run) | (a′) froze every trade for five sessions before an ex-date, with N "not derived". **(a) blocks buys only, over offsets −2..+1, derived (§3.2), and releases at e+2.** The (a′) note's warning applies: "Choosing N = 5 from the table above would be fitting it" |
| **Distribution data** (failed twice: as a universe filter, and inside the Kalman) | Those used distribution levels and cuts. This uses the calendar position |
| **Stale-price artefact** (the commonest death) | The effect is in price, not NAV (NAV leg [V]). r3 found stale prints carry 0.0% of the window P&L [doc]. Stage 0 flags zero-volume fill days |
| **A control scoring as well as the treatment** (the second commonest) | Two controls per part, each a ½ kill (§9). The placebo is built so that it never overlaps a real window (§4.6) |
| **C5** (KILLED D1 by its lagged-signal placebo: "session drift on the signal's trades") | Execution-timing gains can be generic drift on the signal's own trades. That is why (a) carries placebo calendars **and** a z-blind replication |
| **C4's ex-window share** (MIXED after review) | What the review isolated, the generic calendar effect, is exactly what (b) trades. It is not C4's z-score. C4's 2023+ is not used (§5.2) |
| **NAV tenders (D2), E1, MA-HZ** | Event sleeves on this desk die on costs and on D4. (b) carries D4 as a kill, and its grid will flip sign (§6) |

---

## 3. Part (a): the overlay on the live book

### 3.1 The rule, exactly

**Notation:**
- i is a deployed fund; d is a decision session.
- E_i(d) is the set of i's regular ex-dates **declared on or before d** (DG-X2).
- j = d − e is the session offset (positional on the panel's session index) to such an
  ex-date e.

**The window.** W_i(d) is true if j ∈ [−2, +1] for some e ∈ E_i(d). So the next declared
ex-date is 1 or 2 sessions ahead, or is today, or was yesterday.

**The rule, inside `band_gross_capped`, row by row:**
1. The band computes its move exactly as today: trade to the edge when |gap| > b.
2. The unshortable floor (when supplied) is applied, unchanged.
3. **Then, where W_i(d) is true, the held weight may not rise:**
   cur_i ← min(cur_i, prev_i). "Rise" is any increase in signed weight, which covers adding to
   a long, opening a long, and buying back a short. A decrease passes untouched.
4. The stress cap `_cap_gross` is applied last, unchanged.

**The release.** At decision e+2 (fill at the close of e+3, earning from e+4) the window is
false. The band compares that day's target with the held book and trades only if the gap
exceeds b. **Nothing is queued.** A deferred buy whose target has moved back inside the band
never happens.

### 3.2 How k = 2 was derived, where it sits on the profile, and what was not chosen

**Two premises:**
- Under shift(2), a buy decided at offset j fills at the close of e+j+1. It earns rows e+j+2
  onward.
- The last cum-distribution close is e−1, fixed by the record-date rule in every regime
  (§4.2). The fit puts the end of the decay at +3 [V profile; r6 "fall for three sessions"].

**The derivation.**
- **Fills from e−1 to e+2 (decisions j ∈ [−2, +1])** buy at or after the peak. They earn the
  decay with none of the run-up, so the mechanism alone fixes their sign as a loss.
- **Fills before e−1 (j ≤ −3)** earn part of the run-up. Their sign depends on the run-up's size
  against the decay's, which is an estimated quantity. Including them would mean fitting the
  profile.
- **So the window is j ∈ [−2, +1]: "k = 2" sessions ahead of the ex-date, plus the ex-date
  and the session after it.**

**Where it sits.** This is a check on the seen fit, not a derivation. A_j is the mean abnormal
return a buy decided at j earns through +3. On the 13 [V]:

| j | −7 | −6 | −5 | −4 | −3 | **−2** | **−1** | **0** | **+1** |
|---|---|---|---|---|---|---|---|---|---|
| A_j, 13 (bp) | +3.7 | −1.7 | −7.0 | −13.4 | −20.1 | **−29.1** | **−25.3** | **−13.8** | **−6.5** |
| A_j, 17 (bp) | +4.6 | +2.0 | −2.2 | −7.3 | −12.5 | −23.6 | −20.5 | −10.4 | −5.6 |

- All four declared offsets are negative.
- The cumulative stays negative out to j = −6 on the 13 and j = −5 on the 17.
  [V; the 13's j ≤ −3 entries are arithmetic on the [V] profile.]

**Not chosen:**
- **k ≈ 6** (the largest window whose A_j is still negative on the 13). It is also where the
  first-order gain is greatest: the argmax a sweep of k would return.
- **(a′)'s N = 5.**

Both include run-up fills, so choosing either from this table would be fitting it. The trial
reports k = 1…6 on the test set as a plateau check. **It never chooses k.**

### 3.3 Interaction with the band, the cap, sells and flips

- **The band edge.** A deferred name keeps its held weight while its gap grows. That is the
  only change. Every other name trades exactly as today.
- **The stress cap always wins.** A cap-driven uniform scale-down buys back shorts. That buy is
  **not** deferred, because the cap is applied after step 3. Cells where the cap reduced a short
  inside its window are counted and printed.
- **Sells pass.** The optional "bring a sell forward" variant is report-only (§3.7).
- **A long→short flip** inside the window passes, because it is a decrease. A short→long flip
  is deferred whole. Live, a flip may need two orders [U, landmine 4]; the backtest nets it into
  one row.
- **The live runner's own logic is not modelled:** the opening session, `min_names`, and the
  stale-NAV gate's keep-shares rule. The reference book omits them too, so both sides of D omit
  them (§7).

### 3.4 The harness extension (no new backtester)

- **`band_frontier.band_gross_capped(T, b, cap, unshortable=None, defer_up=None)`.**
  - `defer_up` is a bool frame on T's own index. It is validated exactly as `_unshortable_mask`
    validates its frame: the same index, no unknown ticker, no NaN, bool dtype.
  - Step 3 is applied after the floor and before the cap.
  - **`None`, the default, leaves the code path unchanged.**
- **`band_frontier.ex_window_mask(index, columns, ex_dates, lo=-2, hi=1)`** builds W from a
  declared-date table, positionally. It **raises** on an ex-date that is not a session, and on a
  declaration after its ex-date. It never drops either silently.
- **The no-op proof (Stage 0).** On the frozen fit copies of the panels:
  - the sha256 of the held book `band_gross_capped(T, BAND_WIDTH, MAX_GROSS_STRESS)` must be
    identical before and after the edit, with the cap on and with the cap at `inf`;
  - it must also be identical with `defer_up` passed as an all-False frame.
- **Tests** (`scripts/cef/tests/test_band_gross_capped.py`):
  - pin `None` and all-False against the old loop;
  - one test **fails against the old behaviour**: a True cell blocks an increase and lets a
    decrease through;
  - one shows the cap still scaling a deferred short.
- **`evaluate()` is not edited.**

### 3.5 Scoring and the return basis

- **The series.** D_t = `evaluate(H_overlay, R_tot)["pnl"]` − `evaluate(H_ref, R_tot)["pnl"]`.
  R_tot = `total_returns(R)` (the harness's own, with the split-basis guard).
- **Why total returns decide.** A long deferred past e never receives its distribution. On
  price-only returns, which is what Alpaca paper books, the deferral would score the
  distribution-day price drop as a gain with no cash behind it. That is an accounting artifact
  (r3 §2.6 measured paper's version on C4 [doc]).
- **The price-only D** (the paper view) is reported beside it, labelled. It never decides.
- **Turnover (H2).** If |turn(overlay) / turn(ref) − 1| > 5% on the test set, the reference
  becomes `band_gross_capped` at the width whose test-set turnover matches the overlay's. The
  width is found by bisection on turnover only, never on P&L. `match_band_width` gains a
  visible `policy=` argument for this, with a test.

### 3.6 Controls for (a) (declared before any return)

| control | construction | role |
|---|---|---|
| **placebo calendar** | The identical rule with every declared ex-date moved **+5** and **−10** sessions, pooled; each side also reported alone. +10 is reported only. **Why −10 and not −5:** a −5 window releases buys at the real e−3, so they fill at e−2, inside the real run-up and decay. That is no placebo. −10 is the nearest negative shift clear of the real window | **KILL** if the pooled placebo gain ≥ ½ the real gain, same sign |
| **NAV leg** | The identical H_overlay and H_ref, scored on NAV total returns (NAV + distribution over prior NAV) | **KILL** if the NAV-leg gain ≥ ½ the price-leg gain, same sign: the gain would then be a NAV or mark effect, not the price flow claimed |
| **z-blind replication** | The identical rule on a z-blind book: equal-weight long of the eligible 13 at the deployed book's gross, under the same band and cap. Its buys are rebalancing buys after relative price falls | **Report-only, stated both ways in advance (H14).** If its gain per unit of deferred buy turnover has (a)'s sign, the gain is the calendar, as §2 claims. If not, the gain is an interaction with the z-score (which reads the post-ex fall as cheapening), and §2's account is wrong in detail. **No verdict changes either way** (decision 12) |

### 3.7 Report-only: bring a sell forward

- **A sell triggered inside the window cannot be brought forward causally.** Its trigger is
  unknown at e−2.
- **The causal analogue (a-S):** at decision e−2, whose fill is the peak close e−1, a name
  whose target is below its held weight trades to target even when the gap is inside the band.
- Reported against a turnover-matched reference. **It never decides** (decision 13).

---

## 4. Part (b): the standalone sleeve

### 4.1 Events

An event is (i, e), where i is one of the 17 and e is the ex-date of a cash distribution in the
distribution panel. It is eligible only if all of these hold:
1. **e is confirmed by a second dated source**, and **declared on or before e−1** (DG-X1, X2).
   `event_hold`'s `ann` is the declaration date, so the fill (close of e) is **asserted**
   strictly after it.
2. **i has no other ex-date in (e, e+3].** Otherwise the short would cross a record date.
   13 fit cases, **0** in the test calendar [V].
3. **i is not within ±5 sessions of its own split** (r6's mask).
4. **i's returns are finite on rows e+1..e+3.** Otherwise the event is flagged at Stage 0 and
   needs a ruling. It is never filled with zero.
5. **The H-E basket has at least 3 funds** (§4.3).

Specials are included if they meet rule 1. They are reported as a stratum, as are
distribution-size quartiles. **No size conditioning enters sizing**, because r6's "grows with
size" was seen.

### 4.2 Timing, and the record-date arithmetic in each regime

| regime | dates | ex-date vs record date | a trade on e settles | short opened at the close of e |
|---|---|---|---|---|
| T+3 | fit, to 2017-09-04 | ex = record − 2 business days (FINRA 11140(b)(1), [V notice 2000]) | e + 3 = **record + 1** | not a holder of record: **owes no distribution** |
| T+2 | 2017-09-05 → 2024-05-27 (start date [S]) | ex = record − 1 business day [S] | e + 2 = **record + 1** | owes none |
| T+1 | from 2024-05-28 ([V]: SEC press release 2023-29, `docs/REFERENCES.md`) | **ex = record** [S] | e + 1 = **record + 1** | owes none |

- **In every regime a trade on the ex-date settles one business day after the record date.**
  So a short opened at the close of e is never short over that record date, and a basket long
  bought at the close of e is not entitled either.
- **The cover**, at the close of e+3, crosses no record date of i (rule 2).
- **The last cum-distribution close is e−1 in all three regimes.** So the flow's timing
  relative to e is the same before and after T+1, which is why the test splits T+2 (290 events)
  from T+1 (462) as a stratum [V, dates only].
- **DG-X3 reads every test event's record date** from a dated source and flags any event whose
  ex/record arithmetic breaks its regime's row.

**Positions, under shift(2):**
- Decision rows e−1, e and e+1 hold −u on i. Those weights are filled at the closes of e, e+1
  and e+2, and earn rows e+1, e+2 and e+3.
- Decision row e+2 holds 0, filled at the close of e+3.

### 4.3 The hedge: what was declared, what the calendar did to it, and what is declared now

**The brief offered two hedges:** the same-date equal-weight basket of the other universe funds
not within ±3 sessions of their own ex-date, or a named ETF. `prereg_inputs.py` declared the
first, in its strict form, **before computing anything**: no basket fund has an own ex-date at
positions [p−2, p+6], so no hold row lies in any basket fund's [−3, +3] window.

**The calendar killed it.** Credit-CEF ex-dates cluster: 3,228 fund-ex-dates fall on 791
distinct dates, 4.08 per date, and 88.9% of events share their date with at least 3 funds [V].

| hedge | rule | events with < 3 basket funds | per-event sd (bp) | sd of monthly means (bp) | bias |
|---|---|---:|---:|---:|---|
| strict basket (the brief's, strict form) | no own ex in [p−2, p+6] | **73.1%** (median basket 1) [V] | 189.1 on its 869 events [V] | 128.3 [V] | none, but most events lost and the rest a selected subset |
| looser basket (the brief's literal "±3 of own ex-date") | no own ex in [p−3, p+3] | 33.1% (median 4) [V] | not computed | — | **for the trade**: keeps funds whose run-up falls on the hold rows (their ex at p+4..p+6) |
| **H-E (declared)** | **no own ex-date in [p+1, p+8]** | **6.7%** (median 12); test calendar 5.1% (median 15) [V] | **150.3** [V] | **41.4** [V] | **against the trade only** (below) |
| H-D (r6's benchmark) | equal-weight all 17, same date, incl. i | 0 | 142.6 [V] | 42.2 [V] | mixed: co-ex funds (against) and run-up funds (for) |
| HYG, $1 for $1 (the named ETF) | long HYG | 0 (from 2007-04-11) | 199.9 [V] | 114.5 [V] | none; leaves the CEF-wrapper factor in. MUB is not in `data/etf_daily.parquet` [V] |

**Declared: H-E.** The equal-weight basket of the other universe funds that have **no ex-date
declared at e−1 in [e+1, e+8]**, with finite returns on rows e+1..e+3, fixed for the hold, of
at least 3 funds.

**Why H-E:**
- **The exclusion removes every fund whose own ex-day or run-up (offsets −5..0) lands on a hold
  row.** Those are the funds that would bias the test *for* the trade.
- **Funds that went ex on or before e stay in.** Co-ex funds sit in their own post-ex drift
  during the hold. That biases the test **against** the trade, so the test is conservative.
- **It keeps 93% of events and has a third of HYG's monthly noise.** It is also tradable: every
  leg is a fund Alpaca lists, and the basket is long only, so it needs no borrow.

**What was not chosen, and why:**
- **The strict basket:** the calendar leaves too few funds.
- **The looser basket:** biased for the trade.
- **H-D:** its bias runs both ways.
- **HYG:** it leaves the wrapper factor in, so its monthly noise is 2.8× H-E's, and per-event
  power on the test falls from 0.94 to 0.23 [U on V inputs]. HYG and H-D are reported beside
  H-E; neither decides.
- **No hedge mean was computed for H-E, H-D or HYG.** Only dispersion and calendar counts were
  (`prereg_inputs_b2.py` and `_b3.py` say so in their headers). So the choice was not made on a
  mean.

**Causality.** The basket is formed from ex-dates **declared at e−1** (DG-X2). A basket fund
whose undeclared ex-date later lands in [e+1, e+8] stays in, because that is what a trader
would hold. Such cells are counted as calendar surprises, and their price-only/total gap is
printed.

### 4.4 Sizing (every number read through `scripts/cef/spec.py`)

- **The raw sleeve.** u = 1 per event: $1 short i, $1 long basket. Legs on one ticker are
  summed across concurrent events (`event_hold` nets them).
  - **Equal notional is the fixed risk unit.** Per-event dispersion is nearly uniform across the
    17: 209.8bp for taxable funds and 183.0bp for munis under HYG [V]. And it is the unit the
    measured statistic and the power use.
  - Inverse-vol units are a robustness row (decision 14).
- **The sized sleeve:** k × raw, with k = `spec.VOL_TARGET` ÷ σ_active.
  - σ_active is the raw sleeve's annualised daily gross P&L sd **on fit sessions with at least
    one event held**: the NAV-tender rule, so no idle-day top-up.
  - k is computed once at Stage 0, printed and **committed before the test set opens**. It is a
    scale constant, so the Sharpe does not depend on it.
- **The tradable sleeve.** `_cap_gross` at `spec.MAX_GROSS_STRESS`, row by row. The binding
  share is reported. Dates with up to 15 co-ex funds occur (max 15 [V]).
- **Live,** the cap is the combined book's (§7).
- **Capacity** is reported, never deciding. It covers whole-share rounding at
  `spec.CAPITAL_USD`, and participation at $100k, $1m and $10m against 63-session ADV ending e−2.

### 4.5 The evaluator

| piece | code | changed? |
|---|---|---|
| H from legs | `band_frontier.event_hold` (legs `(ticker, first=e−1, last=e+1, weight, ann=declaration date)`) | no |
| daily P&L, shift(2) | `band_frontier.evaluate(H, R)` | no |
| cap | `src/deploy/sleeves/cef_discount.py::_cap_gross` | no |
| borrow | `band_frontier.borrow_charge(H, fee_pct)`: 102% collateral, actual/360, `uncovered` reported | no |
| grid | `band_frontier._stats(pnl, turn)` at 5 / 15 / 30bp on Σ\|ΔH\| | no |
| bar, HAC, bootstrap | `validate._dsr`; `w4_artifacts.nw_t`, `stationary_boot` | no |
| Stage-0 block | `data_guards.require_stage0_rulings`, `stage0_rulings_template`, `guard_closes` | no |

**New code is one trial script**, `scripts/events/exdrift_trial.py`, written after approval, with
tests. It asserts:
- that per-event P&Ls sum to `evaluate(H_raw, R)["pnl"].sum()` (the draft's helper does the same
  [V]);
- that R is finite on every held cell, because `evaluate()` would book a NaN as 0;
- **that price-only and total returns are equal on every held cell**, the "neither owes nor
  receives" property. A mismatch is a calendar surprise and is counted.

### 4.6 Controls for (b) (declared before any return)

| control | construction | rule |
|---|---|---|
| **placebo calendar** | Each event's e is moved **+5** and **−10** sessions positionally. The same eligibility, H-E rule and hold apply relative to the placebo date. **A placebo event survives only if none of its hold rows lies within [−3, +3] of a real own ex-date** (r3's rule) | **KILL** if the pooled placebo mean ≥ ½ the real mean, same sign |
| **NAV leg** | The same events and baskets, on NAV total returns (NAV + D over prior NAV) | **KILL** if the NAV-leg mean ≥ ½ the price-leg mean, same sign |

**Why −10 replaces the brief's −5.** A −5 placebo's hold rows e−4..e−2 always fall inside the
real event's own [−3, +3] window, so **0 of 3,201 fit and 0 of 736 test events survive** [V,
calendar only, `prereg_placebo_counts.py`]. −10 is the nearest negative shift that clears it.
Survivors:

| | +5 | −10 | +10 |
|---|---:|---:|---:|
| fit | 3,126 | 3,108 | 3,082 (reported) |
| test | 731 | 730 | 725 (reported) |

This replacement was chosen on a calendar count, not on a return (decision 8).

**(b) is z-blind by construction**, so it needs no z-blind control. Reported only: the event
mean split by the deployed z at e−1 (rich vs cheap). That shows how much of (b) the book
already owns.

---

## 5. The test set (exact)

### 5.1 The set

**(b), the 17 credit CEFs (the team lead's ruling to make, decision 5).**
- Events: every eligible event with ex-date e ≥ 2023-01-01 whose cover row e+3 is on or before
  the price panel's last session.
- Its end is frozen at Stage 0 as the earlier of:
  - the refreshed distribution panel's last ex-date;
  - the price panel's last session minus 3.
- **Today (dates only, [V]):**
  - prices run 2023-01-03 → 2026-10-15, **950 sessions**;
  - the distribution panel's last ex-date for the 17 is **2026-09-03**, so DG-X1 must refresh it;
  - **752 events (575 on the 13) on 169 dates in 45 months**; 205 a year in 2023, 2024 and
    2025, and 137 in 2026 to date;
  - **714** have an H-E basket on the calendar (**537** on the 13);
  - every ex-date is a session.

**(a), the 13**, sessions 2023-01-01 → the same last session, on the same refreshed calendar.

**Opened once, together, in one run** that writes both parts' statistics before either is read.
Even if (a) runs, that is one opening of the set for this mechanism.

### 5.2 What has already been seen in 2023+, disclosed

| what | seen how | effect on cleanliness |
|---|---|---|
| **C4's 74 family funds, 2023 → 2026-09-30** | C4's holdout was opened on 2026-10-18, and its ex-window P&L share seen: **82.1% committed, 52.6% corrected** [doc r3 §0]. No overlap with the 17 [V: `data/cef_families/universe.csv`] | **Not clean for this hypothesis. Not used.** At most report-only, after the verdict commit (decision 10) |
| **The 17's 2023+ prices** | The discount strategy's book-level P&L: the old CEF holdout opening, verdict FAIL (`docs/SYSTEM.md` §2 [doc]); `band_frontier`'s 2023–26 era rows; the spec's "2023-26 era net Sharpe 0.30" [doc] | **Not conditioned on ex-dates, as far as was checked.** A keyword search of `results/`, `scripts/` and `docs/` on 2026-10-27 for ex-window terms hit W4, `CORE_SIGNAL_CANDIDATES`, C4's files and today's screens. Those were read, and are fit-only or C4's families. The event-catalogue hits (`results/events/...`) were not read in full [U] |
| **The distribution leg on the band's holdings, 2023–26: +0.25%/yr** | `docs/REFERENCES.md` row of 2026-09-09: Σ H·D/P over 3,962 ex-dates, 2005–2026 [doc] | It touched 2023+ ex-dates, but as the **cash** leg, not the price path. It says nothing about the drift |
| **The live paper book, 2026-09-29 →** | It traded the 13 through their Sept and Oct 2026 ex-dates; book-level P&L was read daily [doc `docs/SYSTEM.md` §4–5] | Inside the test window. Book-level only; disclosed |
| **This draft** | 2023+ ex-date **dates**, session dates and basket sizes (calendar) | Counts only; no return |

### 5.3 Forward paper: an alternative, or a second confirmation

- **As the decision set it is too weak (13 names, [U on V inputs]):**

  | months of paper | expected t | P(t ≥ 2) | at half the effect |
  |---:|---:|---:|---:|
  | 12 | 1.58 | 0.34 | 0.11 |
  | 24 | 2.24 | 0.59 | 0.19 |

- **The sleeve bar on forward paper is out of reach** at any horizon a decision can wait for.
  At N = 6 it needs a Sharpe of 3.56 over 12 months and 2.51 over 24 [V, `_dsr` inverted].
- **Recommended: forward paper is the H11 confirmation after a PASS (§11), not the test**
  (decision 9).
- **On paper the entry is not the closing auction.** It is a `late_market` fill 8 to 2 minutes
  before the close, so each event records Alpaca's fill P&L and the official closing-print P&L,
  labelled separately.

### 5.4 Eras (H5)

- **Fit, descriptive:** 2005–09, 2010–14, 2015–19, 2020–22.
- **Test:** 2023–24 and 2025–26 rows, plus the T+2 / T+1 split.
- **r6's statistic by fit era, short P&L per event [V, descriptive]:**

  | era | events | short P&L | month t |
  |---|---:|---:|---:|
  | 2005–09 | 777 | +16.6bp | 2.26 |
  | 2010–14 | 866 | +15.7bp | 3.58 |
  | 2015–19 | 978 | +18.4bp | 5.08 |
  | 2020–22 | 605 | +35.4bp | 4.21 |
  | without 2008-09 → 2009-06 and 2020-02-20 → 2020-06-30 | 3,035 | +18.2bp | 7.76 |

- **The effect is not a crisis artifact.** But 2020–22 carries about twice the per-event mean.

---

## 6. Costs and borrow

- **Gross decides** (D19/D20; E1 amendment 1's "ignore fees, just look at PnL"; the 2026-09-28
  ruling "gross P&L headline, cost grid beside it, labelled, never mixed").
- **The grid** is shown at 5 / 15 / 30bp on Σ|ΔH| after netting, for each part, with whether
  the sign flips. For (a) it is shown on the turnover difference as well.
- **Said once, plainly: for real money, (b) is a losing trade at every point of the grid.**
  - Each event unit crosses the spread four times: short in and out, basket in and out.
  - At 5bp that is about 20bp against a fit effect of about 20bp per unit (r6's 20.5bp).
  - At 15bp it is about three times the effect.
  - Netting against the book trims this but does not change its sign [U].
  - **(a) adds no turnover. It is the only form of this effect that real money could keep, and
    it is the one this test cannot power (§10).**
- **Borrow, separately labelled, never deciding (H4).** `borrow_charge` on the short leg, under
  two schedules:
  - **B0**, zero: Alpaca easy-to-borrow and the paper account [doc `docs/REFERENCES.md` §12l];
  - **B-meas**, the IBKR FEE_RATE series in `data/cef/cef_borrow_history.parquet` where it
    covers the hold, with `covered_share` printed. It is read only at the opening.
- **Distributions owed or received:** none for (b) (asserted, §4.5). For (a), they are inside
  total returns.

## 7. Divergences from the backtest, stated up front

1. **Paper has no closing auction.** Entries and exits fill as `late_market` market orders at
   the quote (`CLAUDE.md` rule 3 exception). Both P&Ls are recorded. The exception never
   applies to a live account.
2. **Borrow existence is assumed in the test, not observed.**
   - Live, only names `shortable` at the decide are shorted; hard-to-borrow is allowed if
     shortable (2026-09-28 ruling).
   - NAD, NEA, NVG and NZF were not shortable at Alpaca on 2026-09-28 [doc].
   - On 2026-10-16, MHD and MQY also read not shortable [doc E1 §5.1].
   - `borrow_status` changes daily (landmine 5).
   - The 13-name stage (§9.1) is the nearest testable proxy. An Alpaca-shortable-today stratum
     is reported; it selects on future information, so it never decides.
3. **One account, netted orders.** Inside the CEF account the sleeve nets with the book, one
   order per symbol, because Alpaca rejects opposite sides as wash trades (landmine 2). The
   sleeve's P&L is attributed from a shadow ledger of its own weights. That ledger is a
   deliverable of any release.
4. **Whole shares only** (landmine 3). The basket's legs are small (about 1/12 of an event's
   notional), so the rounding error is reported.
5. **The declared calendar must exist at the decide.** Live, the ex-date and declaration come
   from the nightly collector and Alpaca's corporate-action announcements. A missing or late
   declaration is a missed event, logged and **never back-filled**.
6. **(a) in the harness omits** the runner's opening session, `min_names` flatten and stale-NAV
   keep rule. They are omitted on both sides of D.
7. **The test treats every name as tradable at the close.** The closing auction's 3.3–6.3%
   unfilled rate for non-Russell names is not modelled (the `/prereg` template's figure [doc]).
8. **The distribution panel is yfinance** (`scripts/fetch_cef_distributions.py`). On the fit it
   missed 11 CRSP distributions, three of them large year-end specials [doc `docs/REFERENCES.md`
   row of 2026-10-11]. DG-X1 cross-checks the test set.

## 8. Stage 0: flags, rulings file, and the block

| gate | what | done when |
|---|---|---|
| **DG-X1** | Refresh `data/cef/cef_distributions.parquet` through the price panel's last session with `scripts/fetch_cef_distributions.py`. Cross-check every 2023+ ex-date and amount against a second dated source: CRSP `ret ≠ retx` to 2024-12-31; after that, Alpaca corporate-action announcements or sponsor notices (`scripts/data/fetch_sponsor_notices.py`). The research run writes the refreshed panel **outside `data/`** (landmine 9) | every event agrees, or carries a flag with a ruling |
| **DG-X2** | A **declaration date** for every test ex-date of the 17, from a dated source. **No tracked panel holds one** [V: the panel's columns are `ticker, grp, ex_date, amount, stock_split`]. Alpaca `GET /v1/corporate-actions` exists; its depth for these CEFs in 2023–26 is [U] (`docs/REFERENCES.md`: "coverage thin before 2020") | every event has a declaration ≤ e−1, or is excluded and counted |
| **DG-X3** | Record dates, and the ex/record arithmetic of §4.2 per regime | every break flagged and ruled |
| **DG-X4** | Price bars: `guard_closes` (spike-and-revert), the split-basis guard, and zero-volume fill days on e and e+3 | flags ruled; bar rulings file if any |
| **DG-X5** | NAV on rows e+1..e+3 for the NAV leg. Repeats (NAV(D) = NAV(D−1)) are flagged | coverage printed; flags ruled |
| **DG-X6** | D4 factors to the last test session: French six, IEF, HYG, and **MUB**, which is not in `data/etf_daily.parquet` [V]. It needs a fetcher and a `docs/REFERENCES.md` source note | all cover the test window |
| **DG-X7** | **Identity gates, before the test set is read.** (b): reproduce r6 (3,226 events, −20.454bp, month t −6.765) [V by this draft], and H-E's fit per-event sd of 150.3bp. (a): the no-op hashes of §3.4. Then commit the fit-descriptive table for both parts, k, and the cap-binding share | all pass, committed |
| **DG-X8** | `compute.use_numexpr` off, with the denormal assertion (`scripts/events/numexpr_fault.py`) | passes |

- **The flag table:** `results/events/exdrift/exdrift_stage0_flags_<date>.csv`, keyed on
  `(check, ticker, date)`, one row per flag.
- **The rulings file:** `results/events/exdrift/exdrift_stage0_rulings_<date>.csv`, with the
  keys plus `ruling`, `ruled_by` and `ruled_on`. `stage0_rulings_template` writes the blank form.
- **Bar rulings,** if any yfinance bar trips the guard: `results/events/exdrift/exdrift_bar_rulings_<date>.json`.
- **The block:** both trial scripts call `require_stage0_rulings` **before forming any P&L, fit
  or test**, and refuse, naming the flags, while any flag lacks a ruling.

---

## 9. The order of evaluation: the exact kill rules

**Every statistic of every stage is computed and reported, whatever the verdict.** The verdict
is the first failing rule. Gross, total-return basis. These rules are pre-committed and **are
not softened later.** The test set is opened once, after DG-X7's commit.

### 9.1 Part (b)

| stage | statistic (test set) | rule | if it fails |
|---|---|---|---|
| 0 | DG-X1…X8; the counts reprinted beside §5.1 (H14); k committed | a gate fails | **HALT** to the team lead; no test statistic |
| — | **the test set is opened here; the trial is spent from here** | — | — |
| 1 | per-event mean gross P&L, H-E, 17 names, **month-clustered t** (date-clustered and bootstrap beside it) | mean > 0 **and** t ≥ 2.0 | **KILL D1** |
| 2 | the placebo calendar, pooled +5 / −10 | placebo mean < ½ × real mean (same sign) | **KILL** (not the ex-date) |
| 3 | the NAV leg | NAV-leg mean < ½ × price-leg mean (same sign) | **KILL** (a NAV or mark effect, not the claimed price flow) |
| 4 | the 13-name stratum (the live universe) | mean > 0 | **KILL D6** (real where we cannot trade it) |
| 5 | R-D4 on the tradable sleeve's daily gross P&L: French Mkt-RF, SMB, HML, RMW, CMA, UMD; TERM = IEF − RF; HY = HYG − IEF; MUNI = MUB − IEF; each at t and t−1 (Dimson), betas summed, HAC 21 | alpha t ≥ 3.0 **and** every \|summed β\| ≤ 0.10 at the vol target | **KILL D4** |
| 6 | the bar: `_dsr` on the sleeve's gross daily series at N (decision 4) | > 0.95 | **NEITHER**: real at most, below the bar. No sleeve and no re-test on these data. The team lead rules WATCH or D5 |
| 7 | the verdict is committed | — | — |
| 8 | after a PASS only: paper H11 (§11) | §11 | revert |

**Reported, never deciding:**
- the grid and borrow (§6);
- H-D and HYG rows;
- T+2 / T+1; 2023–24 / 2025–26;
- taxable / muni; specials; size quartiles;
- the +10 placebo;
- declarations ≤ e−2;
- the Alpaca-shortable-today stratum;
- the rich/cheap z split;
- capacity and rounding;
- the inverse-vol unit.

### 9.2 Part (a), if run (decision 3)

| stage | statistic (test set, the 13) | rule | if it fails |
|---|---|---|---|
| 0 | the no-op hashes (§3.4); DG-X1, X2 for the 13; the Stage-0 block | a gate fails | **HALT** |
| — | **opened in the same run as (b)** | — | — |
| 1 | turnover match (H2) | within 5%; otherwise the matched-width reference (§3.5), printed | — |
| 2 | D, gross total-return; NW t, L = 21 | mean > 0 **and** t ≥ 2.0 | **KILL D1** |
| 3 | placebo calendar, pooled +5 / −10 | placebo gain < ½ × real gain | **KILL** |
| 4 | NAV-leg gain | < ½ × price-leg gain | **KILL** |
| 5 | R-D4 on D (the §9.1 set) | alpha t ≥ 3.0, every \|summed β\| ≤ 0.10 | **KILL D4** |
| 6 | `_dsr` on D at N (53 if CEF) | > 0.95 | **NEITHER** |

**Reported, never deciding:**
- the price-only D (the paper view);
- the k = 1…6 plateau;
- the z-blind replication (§3.6);
- a-S (§3.7);
- the grid on the turnover change;
- the borrow change;
- the deferred buys per year and the cap-overridden cells.

## 10. Power, and what we expect [U]

**The inputs are fit dispersion [V] and r6's published mean.** The bar and its sampling error
come from `scripts/xasset/slate_feasibility.py`, which inverts `validate._dsr`. The Sharpe
needed on T = 950 test sessions [V]:

| N | 1 | 6 | 7 | 8 | 53 |
|---|---:|---:|---:|---:|---:|
| Sharpe needed | 0.848 | 1.825 | 1.867 | 1.901 | 2.303 |

**(b), per event (stage 1).**
- **Method.** The SE is the fit's sd of monthly means, 41.4bp, scaled to the test's 15.9
  events a month over 45 months: 5.79bp on the 17, and 6.68bp on the 13.

  | true mean per event | expected t, 17 | P(t ≥ 2), 17 | P(t ≥ 2), 13 |
  |---|---:|---:|---:|
  | 20.5bp (the fit effect) | 3.53 | **0.94** | 0.86 |
  | 10.2bp (half) | 1.77 | **0.41** | 0.32 |
  | 5.1bp (a quarter) | 0.88 | 0.13 | 0.11 |

- **Shrinkage is the expected case.** The effect was found after the fit was seen. So the
  honest planning point is between the half and full rows.
- **Adequate for stage 1 only if the effect survives at roughly two-thirds of its fit size.**

**(b), the sleeve (stages 5–6).** Two estimates of its Sharpe disagree, and neither is used
silently:
- **0.571**, measured through `evaluate()` on the strict basket's 869 events. That subset is the
  27% of events on uncrowded dates (by fit era 0.71 / 0.24 / 0.17 / 1.52 [V, descriptive]).
- **1.78**, arithmetic on H-E's dispersion with r6's mean, equal notional per event [U].
- Rescaling the first by √(3,009 ÷ 869) gives 1.06 [U].

| sleeve Sharpe | P(`_dsr` pass), N = 6 | N = 7 | P(alpha t ≥ 3) |
|---:|---:|---:|---:|
| 0.57 | 0.01 | 0.01 | 0.03 |
| 1.06 | 0.07 | 0.06 | 0.17 |
| 1.78 | **0.46** | 0.43 | 0.67 |
| 0.89 (1.78 at half the effect) | 0.03 | 0.03 | 0.10 |

- **The likeliest verdicts:** a stage-1 pass followed by **NEITHER** at the bar, or a D1 if the
  effect has shrunk to half.
- **A PASS needs the effect at about its fit size in 2023–26**, on a test of about 3.8 years.
- **Is this power adequate?** For stage 1, marginally. **For the bar, no**, unless the effect is
  at full strength.

**(a), first order.**
- **In the fit,** from 2013-06-21 to 2022-12-30 (9.5 years), the deployed band made 276 buys
  in the window, 29.0 a year. They were 1.011× capital a year: 14.9% of buy turnover. The window
  holds 19.3% of held name-days [V].
- **The first-order gain** from moving every one of them past +3 is +17.0bp/yr of capital,
  with sd 41.4bp/yr: a gain Sharpe of 0.41 [U on V inputs].
- **On the test:** expected t 0.80; P(t ≥ 2) 0.11; P(`_dsr` pass) 0.003 at N = 6 and 0.000 at
  N = 53.
- **(a) cannot be decided on this test set.** That is the reason for decision 3.

**Expected readings** (being wrong here is fine, and is the point):
- (b) stage 2 passes: the +5 placebo sits in the quiet post-ex days.
- Stage 3 passes: the fit NAV leg was −0.63bp.
- Stage 4 likely passes: the 13 carried +25.3bp, t 6.15, in the fit [V].
- **Stage 5 is uncertain.** H-E is dollar-neutral within credit CEFs. Its 3-day holds should
  carry little factor beta, but the HY and MUNI betas are unmeasured.

## 11. What would falsify it once trading (H11)

Stated now, for a (b) sleeve that passed and was released:

- **Only broker-confirmed fills count.** For each event, paper records:
  - Alpaca's fill P&L (the official record: end-of-day history, the 2026-10-19 ruling);
  - the official closing-print P&L;
  - both labelled, never blended.
- **Fidelity, per event.** Each live event's declaration read, decide, entry, basket, cover and
  netted orders must match the declared rule run on the same inputs. A mismatch halts the
  sleeve as a bug. A missed event is logged and counted, never back-filled.
- **Reversal.** Read at 12 and at 24 months after arming. Reverse if the mean live per-event
  gross P&L is below the 5th percentile of the trial's own test-set per-event means resampled
  by month. That percentile is re-measured on the read date. **No threshold is written here as
  a number (H14).**
- **Pause, not kill.** A live drawdown beyond the test set's worst, re-measured, stops new
  entries. Open events run to their cover.

For (a), if it ever ran and passed: the live deferred-buy count per year and the shadow D,
read at 60 live sessions as the book's own kill rule is, and reversed if D's mean is below zero.

## 12. Trial accounting

- **Today** (`docs/RESEARCH_STATE.md`, read 2026-10-27): **EVENTS 2, CEF 52.**
  **`docs/RESEARCH_STATE.md` changed in this draft: no.**
- **If approved as recommended:**
  - EVENTS 2 → 3, (b), in the approval commit. Its bar is at N = 7 (decision 4).
  - CEF stays at 52, because (a) is withdrawn on power (decision 3).
  - If (a) is run instead: CEF 52 → 53, bar √(2 ln 53) = 2.818.
  - The same commit records N and updates the counter table (`/prereg`).
- **Sealed sets:**
  - The 2023-01-01 time holdout is opened once, for this mechanism, after DG-X7.
  - **The 27 names are not read and not consumed.** The trial script asserts it by ticker.
- **Zero-trial helpers:** this folder's five scripts.
- **Trial scripts, after approval:**
  - `scripts/events/exdrift_trial.py` for (b);
  - for (a), the `band_gross_capped(defer_up=...)` and `ex_window_mask` extension, with tests,
    and `scripts/cef/ex_buy_defer.py`.

## 13. What this does not test

- **The real-money version.** Costs and borrow are shown and decide nothing. The real-money cost
  gate remains the gate for any capital (2026-10-09 ruling).
- **The pre-ex run-up long** (buy at e−3, sell at the close of e−1). It is a different trade,
  and its profile was seen.
- **C4's equity families**, whose 2023+ is spent, and any non-credit CEF.
- **The 27 sealed names**, and the IBKR route for the four munis' shorts (IBKR waits for a
  trigger).
- **Distribution-size or special-only conditioning.** Reported as strata only.
- **(a′)'s freeze-all-trades variant**, and any k chosen from the profile.
- **Intraday or opening-auction timing of the entry** (C5's question).
- **Options**, and any hedge beyond H-E (HYG and H-D are reported only).
- **Whether the flow is retail.** The "who" of §2.2 stays [U]. Nothing here identifies the
  traders.

## 14. Open questions for the team lead (each with a recommended answer)

1. **One trial or two?** Recommended: **two.** (a) and (b) are separate decision rules on
   separate P&L series.
2. **Which counter carries (a)?** Recommended: **CEF**, under the 2026-10-09 ruling "Changes to
   the live CEF book stay on CEF". That is trial 53, bar 2.818. The alternative is EVENTS at
   (b)'s N.
3. **Spend (a) now?** Recommended: **withdraw it on power before any data step**, as XASSET's
   X5 was withdrawn (expected t 0.80, P(t ≥ 2) 0.11, P(bar) ≈ 0). Keep the design here.
   - If (b) passes, revisit (a) only on forward data, because 2023+ will then be known to
     contain the drift.
   - Alternative: run it as CEF trial 53 in the same opening as (b).
4. **N for (b)?** Recommended: **N = 7** (√(2 ln 7) = 1.973; Sharpe needed 1.867).
   - N = 6 was fixed for six named EVENTS tests (E1–E4, NAV tenders, the merger-arbitrage
     reconstruction); this is not one of them.
   - Alternative: N = 6, if the team lead rules a slot withdrawn (MA-HZ has been WATCH, no
     trial, since 2026-10-20). That changes P(pass) by 0.03.
5. **(b)'s clean test set.** Recommended: **the 17, 2023-01-01 → the last panel date, as the
   team lead's ruling**. Alternative: forward paper only (§5.3).
6. **Headline names.** Recommended: **the 17**, the pre-specified set, **with the 13's sign as
   stage 4**. Alternative: the 13 only (P(t ≥ 2) 0.86 vs 0.94 at the fit effect). The fit's
   taxable/muni split was seen, so it is not a candidate.
7. **The hedge.** Recommended: **H-E** (§4.3). The brief's strict basket leaves 73.1% of events
   untradable; its looser form is biased for the trade; HYG is 2.8× noisier.
8. **The placebo.** Recommended: **+5 and −10, pooled**, because a −5 placebo cannot exist
   (0 survivors) [V]. Alternative: ±10.
9. **Forward paper.** Recommended: **the H11 confirmation after a PASS**, not a decision set.
10. **C4's families in 2023+.** Recommended: **do not compute.** If wanted, report-only after the
    verdict commit.
11. **Data pulls.** Recommended: **approve** DG-X1 (the distribution refresh and second source),
    DG-X2/X3 (declaration and record dates: Alpaca corporate-action announcements, then sponsor
    notices) and DG-X6 (MUB). Any credentialed fetch stays the team lead's.
12. **What "z-blind" means for (a).** This draft reads it as **a z-blind replication** (§3.6,
    report-only, both outcomes stated). Alternative: a random-date deferral as a third ½ kill.
13. **Bringing sells forward.** Recommended: **report-only (a-S)**, and only if (a) runs. A sell
    triggered inside the window cannot be moved earlier causally.
14. **Sizing.** Recommended: **equal notional per event × k**, with k = `vol_target_annual` ÷
    σ_active (fit, frozen). Alternative: inverse-vol units.
15. **Live basket for (b).** Recommended: **the 17 as longs where Alpaca lists them as
    tradable**, under (b)'s own sleeve spec. The four munis can be bought; only the short is
    blocked. Alternative: the 13 only, at the cost of a thinner basket.
16. **When the counter moves.** Recommended: **in the commit that records approval** (E1's
    convention).
17. **Decision basis.** Recommended: **gross P&L decides; the grid and borrow are beside it**
    (E1 amendment 1). Confirm that it applies to a three-session trade known to be D2 for real
    money.

## 15. Reproduce this draft's inputs

```bash
cd results/events/prereg_exdrift      # from the repo root
python3 -I -B prereg_inputs.py           # gate (r6 reproduced), profile, strict basket, NAV leg, (a) counts, test dates, power
python3 -I -B prereg_inputs_b2.py        # r6 by era and by group; HYG dispersion only
python3 -I -B prereg_inputs_b3.py        # H-E and H-D: calendar feasibility and dispersion only
python3 -I -B prereg_power_he.py         # power on the clean set under H-E
python3 -I -B prereg_placebo_counts.py   # placebo survival, calendar only
```

They were run on 2026-10-27 from a scratch export of `simon` at `dff4b5c` (with `data/` symlinked); they now read the repo root's `data/`, read-only, and
write only to this folder. The first writes fit-cut copies of the core panels to `_cache_panels/` (gitignored).
