# Pre-registration: C4's discount level against family peers, as a second signal in the C4 account (CEF trial 54)

Date: 2026-11-02 (finalised the same day)   Counter: **CEF trial 54**   Author: idea-generation seat
**Status: APPROVED 2026-11-03 by the team lead; CEF 53 → 54 in the commit that records it** (`docs/RESEARCH_STATE.md`,
`docs/SYSTEM.md` §5 "Team lead, 2026-11-03"). No 2023+ return of this signal had been computed at approval.

> **§0.A — the approval (team lead, 2026-11-03, answered interactively).**
> - **Gate 0: cleared, post-data.** The team lead's words: "I approve, lets try and deploy as fast as possible". The
>   evidence was §4b (commit 389f61a, reproduced byte for byte 2026-11-03). It is a judgment on seen data, **not a
>   pre-registered pass**.
> - **Open questions 2–9: the recommended answers, all accepted**, with "use the 2 accounts I gave you, i dont hvae
>   any other": the book is the core account plus the C4 (spare) account, and no third account.
> - **"As fast as possible" changes no rule.** §6.2 is unchanged: the data gates, then P1 at NW t ≥ 2.825, P2, K1–K3,
>   P3, then the holdout opened once. Speed comes from running the stages back to back and building the sleeve key
>   in parallel, never from skipping one.
> - Files this note calls "in this folder" are in `results/cef/screens_2026-11-02/`.
>
> **2026-11-03 (later), K3 OVERRIDDEN POST-DATA by the team lead.**
> - **K3 (D4) FAILED as committed.** The level-only book's post-2007 alpha is t 2.96 < 3.0, and every |β| ≤ 0.082.
>   The failure is significance, not factor exposure.
> - **The team lead overrode it post-data,** asked interactively on 2026-11-03 after seeing the KILL: "revive it and
>   figure out a way to not kill it". The coordinator had recommended recording the KILL and was overruled.
> - **This is NOT a pass of K3 and must never be described as one.**
> - **P1 is lag-fragile.** Its t is 2.8271 at the automatic lag 6 on the residual, as committed, and 2.791 at lag 5 on
>   the dependent series, against a bar of 2.8245.
> - **The trial continues under the pre-registered remainder:** P3, then DG-L4, then the 2023–26 holdout opened once.
>   **The holdout's result is decisive.** The override covers K3 only. A failure at P3, DG-L4 or the holdout is a
>   KILL.

The team lead chose on 2026-11-02 to take this signal to a pre-registration. The evidence is the zero-trial
screen `screens_2026-11-02/ALPHA_SLATE.md` §S5 (fit only, yfinance return leg). The design inputs are in
`prereg_c4_level_design.py` → `prereg_c4_level_design_output_v4.txt` (C4's v4 spec; the first run at v3 is
`prereg_c4_level_design_output.txt`). On approval this file moves to
`results/cef/PREREG_C4_LEVEL_2026-11-02.md` (open question 9); done 2026-11-03, the draft path deleted (git keeps it).

## 0. The answer in one table

| item | answer |
|---|---|
| **what changes** (§1) | One new optional frozen key in C4's spec, `level_signal`. **Absent, C4 is today's book byte for byte.** Present, C4's unit target becomes an equal-risk blend of its z target and a within-family discount-level target, through the same vol scalar, multiplier, band and **the same 1.90 gross cap** |
| **the split** (§3) | **Half the ex-ante risk on each signal.** Derived from the two-sleeve mean-variance rule on fit inputs (gives 0.514 on z at C4's v4 spec, ×1.26; 0.515 at v3's ×1.27) and rounded to equal risk. Plateau: SR 1.442–1.547 across 0.30–0.70 (1.443–1.549 at ×1.27); the derived 0.50 is also the grid's argmax, so nothing was moved toward it |
| **the shared cap** (§3.3) | Kept at 1.90 (a margin rule, not a tuned parameter). On the fit at C4's spec multiplier (v4: ×1.26) the blend's held book sits at the cap on **28.3%** of sessions, against 21.5% for z alone (29.0% / 22.0% at v3's ×1.27). Turnover falls from 48.5 to **32.9** turns a year (48.9 → 33.2 at ×1.27) (construction properties only; no P&L of the blend computed) |
| **Gate 0** (§4b) | Survivorship, with dead funds included, run **before approval**. **A team-lead judgment on the result** (ruled 2026-11-02: "keep it flexible and make judgment off results"), recorded **post-data** in `docs/SYSTEM.md` §5. It is evidence, **not a pre-registered gate**. `gate0_analysis.py` reports the ratio with 95% CIs, the sign test, and the verdict under both candidate rules (≥ 0.5, ≥ 0.75) with each one's power and false-alarm rate. Pull 1 (CRSP) was too thin; pull 2 (EDGAR N-CSR) is running **2026-11-03 evidence: b_D/b_A 1.36 (CI 0.80–2.13), sign test 30 of 33, both rules met; coverage 0.642; stress bound 1.03. Recommendation: proceed** |
| **pass rule** (§6.2) | Fit: the level book's spanning alpha on C4's z book, **NW t ≥ 2.825** (√(2 ln 54)). Also the deflated-Sharpe bars at declared N = 54, NC1, the placebo and D4. Then the 2023–26 holdout's **sign** (the C4 precedent). Net at 15bp is reported (D2 label) **Unchanged by the Gate 0 ruling, and still pre-registered** |
| **stops** (§6.3) | C4's own kill rule and the trial-53 stops, **rebuilt on the blended book**, plus L1: the level component's modelled 120-session P&L below its fit 5th percentile → revert the key |
| **revert** (§9) | Delete `level_signal` from C4's spec |
| **expected** (§5) | +0.4 to +1.0%/yr gross on all capital [model, U] after the cap haircut; the blend's ex-ante SR about 1.5 vs 1.18 uncapped |
| **open questions** (§10) | ten, each with a recommended answer (the tenth: amendment A1, after pull 1 proved too thin) |

---

## 1. What changes

### 1.1 The key, the file, the value

> **CORRECTED 2026-11-03.** This pre-registration was first written against `c4_families.v3.20261102` (branch
> `c4-rel`, 8b14298, dark), at `sizing_multiplier` 1.27. Trial 53 amendment 1 then put C4 on `main`
> (f27ef81, tag `release-20261103-1`) as **`c4_families.v4.20261102`, ×1.26, cap 1.90**. So:
> - the trial's spec becomes **v5**, and the no-op test diffs against **v4**;
> - every C4 multiplier below is read from C4's spec at run time, not written as a literal;
> - the construction figures (§3.1 and §3.3) and the account figure (§5) were re-measured at v4 with
>   `prereg_c4_level_design.py`, fit only, with no blend P&L, and sit beside the v3 values;
> - the v3 run reproduces byte for byte with `--spec-ref c4-rel`.

| spec | file | today | after |
|---|---|---|---|
| C4 | `ops/specs/c4_families.frozen.json` (on `main` at f27ef81; tag `release-20261103-1`) | `c4_families.v4.20261102`; key absent | **`level_signal: {"risk_share": 0.5, "family_of": {<ticker>: <family>, ... 74 rows>}}`**, spec id **v5** |

- `family_of` is C4's frozen family map (`results/cef/c4/c4_universe_frozen_2026-10-14.csv`, column `family`),
  copied into the spec so the sleeve reads no second file.
- **Nothing else in the spec moves:**
  - `vol_target_annual` 0.06, `sizing_multiplier` (1.26 at v4, trial 53 amendment 1), `band_width` 0.048 and `max_gross_stress` 1.9;
  - `z_window` 252, `min_adv_usd` $3m, `min_names` 6 and `min_abs_weight` 0.005;
  - the masks, and the `risk` block.

### 1.2 What the sleeve does with it

The blend is built inside `src/deploy/sleeves/cef_discount.py::target_positions`, on the date-t panel only (H7):

1. **w_z**: today's unit-gross z weights, −(z − mean z), on today's eligible names.
2. **w_L**: on the same eligible names, −(discount − its family's mean discount), unit gross. A family with
   fewer than 2 eligible names contributes zero. The discount is the panel's own `disc` (price against NAV),
   with C4's M1|M2 masks applied as they are to the z.
3. **Risk equalised.** s_z and s_L are the trailing realised vols of the two unit-gross books, using today's
   weights on the last 63 sessions of price returns through t. That is the estimator `build_targets` already
   uses for its vol scalar. mix = ½·w_z/s_z + ½·w_L/s_L, renormalised to unit gross.
4. **One vol scalar, the existing one:** target = mix × clip(0.06 / s_mix, 0.2, 2.5).
5. From here **today's code path runs unchanged:** the account holds m × the unit target, the band compares it
   with held / m, `_cap_gross` acts at 1.90 / m in unit weights, and the dust filter reads the unit weight.

When the key is absent, steps 2–4 do not run, and w_z × its scalar is today's target.

### 1.3 Tests, each shown to fail against the old code before it is kept

1. **Key absent: byte-identical** to `c4_families.v4.20261102` on the real panel and on the synthetic one. It
   covers plan.json, plan_sha, orders, targets and the run record, as the trial-53 pins do.
2. **Key present with `risk_share` 0** (all risk on z): identical to absent.
3. **Equal risk:** on a synthetic panel with known vols, the blend's ex-ante risk contributions are equal to
   1e-12.
4. **Families:** a ticker without a family raises. A one-name family gets zero level weight.
5. **The cap:** the emitted gross is ≤ 1.90 × NAV.
6. **C4's fidelity probe passes:** `scripts/cef/c4_paper_benchmark.py` gains the same blend, so the HALT rule
   still compares like with like.
7. **The combiner refuses** a `risk_budget` sleeve whose spec carries the key, as it refuses `sizing_multiplier`.

---

## 2. Why, mechanically

**The mechanism.** Retail yield buyers overpay for some funds' brand or distribution rate. The arbitrage is a
short of the premium fund, whose lendable pool cannot grow (no creation). Borrow is dearest exactly there, and
idiosyncratic risk binds (Pontiff 1995 [U on magnitude], Pontiff 2006 [S]; `docs/REFERENCES.md`). So premium
funds underperform their peers and discount funds outperform, over months. **The loser** is the holder who
pays the premium.

**The z cannot see it.** C4's z is standardised against each fund's own 252-session history, so a fund that has
sat 10pp rich of its peers for a year has z near zero. **It is not fair value in costume, in these families.**
The NAV leg of the fit slope is −0.26bp/pp (t −0.32). On the credit core the same test fails exactly there: its
NAV leg is +1.17bp/pp (t +3.01), which is why the trial is C4 only (`ALPHA_SLATE.md` §S5).

---

## 3. How the parameters were derived

### 3.1 The risk split

The rule: for two unit-vol strategies with Sharpe s1, s2 and correlation ρ, the mean-variance risk weights
are ∝ (s1 − ρ s2, s2 − ρ s1). The inputs were measured on the fit, 2005-02-22 → 2022-12-30, total return, on
the series the screen had already seen [V `prereg_c4_level_design.py` §A]:

- s_z = 1.176 (C4's v4 spec book, ×1.26, cap 1.90; 1.178 at v3's ×1.27);
- s_L = 1.123 (the level book);
- ρ = +0.104.

The weights come out 1.071 : 1.011, which puts **0.514 on z** (1.073 : 1.011 and 0.515 at ×1.27). Two Sharpes
estimated this noisily do not support 0.514 over ½, so **the derived value is equal risk, 0.50.**

**The plateau** (an equal-weight-of-risk blend of the two unit-risk series, fit, already seen):

| share of risk on z | 0.30 | 0.40 | **0.50** | 0.60 | 0.70 |
|---|---|---|---|---|---|
| Sharpe, v4 (×1.26) | 1.442 | 1.515 | **1.547** | 1.530 | 1.469 |
| Sharpe, v3 (×1.27), first run | 1.443 | 1.517 | 1.549 | 1.531 | 1.471 |

The surface is flat within 0.03 Sharpe across 0.40–0.60, and the derived value sits on top of it. **The grid's
argmax is also 0.50.** It was not chosen from the grid: the rule gives 0.514 (0.515 at ×1.27) before the grid is read.

### 3.2 The level's construction

The construction was declared before the screen's first run (`alpha_level.py` docstring) and never varied:
within family, unit gross, the raw discount level, and z-blind.

- **Not chosen:** a pooled level across families, never run, because `docs/SYSTEM.md` says that is a
  permanent group bet.
- **Not chosen:** a monthly calendar refresh, which the screen's book used. The live policy is the band (H8:
  the band width was derived by the cube-root law). The trial measures the daily level through the band.

### 3.3 The shared 1.90 cap

`max_gross_stress` 1.90 is C4's margin rule, re-derived by the core's frozen rule (`docs/SYSTEM.md` §5), and
it is not re-tuned for this trial. Lower correlation means more gross per unit of risk, so the cap binds more
often. Construction properties on the fit, band 4.8%, at C4's spec multiplier: v4 (×1.26, re-measured
2026-11-03, `prereg_c4_level_design_output_v4.txt`) beside the first run at v3 (×1.27,
`prereg_c4_level_design_output.txt`) [V `prereg_c4_level_design.py` §B]:

| book | target gross | target > cap | uncapped held gross | held gross | at the cap | turns/yr |
|---|---:|---:|---:|---:|---:|---:|
| z only, v4 (×1.26) | 1.513 | 22.4% | 2.101 | 1.550 | 21.5% | 48.5 |
| **blend ½ : ½, v4 (×1.26)** | **2.279** | **72.0%** | **2.536** | **1.719** | **28.3%** | **32.9** |
| z only, v3 (×1.27) | 1.525 | 23.2% | 2.118 | 1.556 | 22.0% | 48.9 |
| blend ½ : ½, v3 (×1.27) | 2.298 | 72.6% | 2.556 | 1.722 | 29.0% | 33.2 |

The cap scales the whole held book by one factor, so it takes risk from both signals in proportion. The split
survives the cap; the account's level of risk does not. That haircut is in §5.

---

## 4. Committed in advance

- **Execution:** shift(2) through `scripts/research/harness.py` (`band_frontier.band_gross_capped`, then
  `evaluate` / `report`). No new backtester.
- **Score:** gross P&L is the headline, total return, on **CRSP primary returns as C4's fit used**, with the
  yfinance leg as the second source. Price only (paper's P&L of record) sits beside it. The 5 / 15 / 30bp grid
  is labelled as the real-money view. Borrow gets its own column, not charged on paper.
- **Eras:** C4's: 2005–09, 2010–14, 2015–19, 2020–22; holdout 2023–26.
- **Fit ends 2022-12-30**, asserted in every helper.
- **Holdout 2023-01-03 → 2026-09-30**, the window C4's own holdout used. Opened once, after the fit verdict's
  commit.
- **Turnover matching (H2):** the z-only reference is re-run at the band width that matches the blend's
  turnover within 5% (`band_frontier.match_band_width`), and the comparison is made there.
- **Negative controls:**
  - NC1, the NAV leg of the level slope (must stay |t| < 2);
  - the within-family shuffle placebo (20 draws, seed 20261102).
- **Declared seen:**
  - every figure in `ALPHA_SLATE.md` §S5 and in `prereg_c4_level_design_output.txt` (fit);
  - C4's 2023–26 returns, which were opened for trial 52 on 2026-10-18 (the z book, not this signal).

### 4b. Stage 0: Gate 0 first, then the data gates. No P&L of any kind before every gate is clear

**Gate 0 — survivorship, run before the approval commit** (open question 1), on fit data only:

> **RULED 2026-11-02 (the team lead): "keep it flexible and make judgment off results".**
>
> - **Gate 0 is a team-lead judgment on its result, not a mechanical gate.** The rules in the table below (and
>   amendment A1's 0.75) stay as the declared reference points. Neither one decides.
> - **The caveat, plainly.** A gate decided after its data have been seen is not a pre-registered gate. Gate 0 is
>   evidence for the team lead's judgment. It cannot claim a pre-registered pass, and the record must not describe
>   it as one.
> - **What the evidence is.** `gate0_analysis.py`, which writes `gate0_analysis_output.txt` and `.json`. It
>   reports:
>   - b_D / b_A (dead against survivor slope) and b_B / b_A (all funds against survivors), each with a 95% CI from
>     (1) a bootstrap by fund-half-year, the headline, and (2) a bootstrap by calendar half-year as a second
>     method. The two are reported side by side and not averaged;
>   - the sign test: the share of half-years whose dead-only slope is negative, a binomial p, and P(b_D ≥ 0);
>   - the verdict under both candidate rules, ≥ 0.5 (the original) and ≥ 0.75 (A1), each with its power
>     P(flag | halving) and false-alarm rate P(flag | r = 1) at the realised NAV coverage. For reference, at full
>     coverage the power is 0.50 and the false-alarm rate 0.00 for ≥ 0.5, and 0.97 and 0.03 for ≥ 0.75
>     (`gate0_coverage_output.txt`);
>   - coverage, the calibration agreement, and two sensitivities: cells of family × period-end month (primary,
>     declared before any dead-fund NAV was read) against family × half-year, and with the dead funds whose names
>     go unclassified excluded.
> - **The record.** The team lead's Gate 0 call goes into `docs/SYSTEM.md` §5 with its date, labelled
>   **"post-data"**. It names the evidence file's commit and the reasons in a sentence. A negative call means no
>   approval and no trial; a positive one leaves §6.2 to judge the trial.
> - **What does not change.** The trial's own pass rule (§6.2: the fit's spanning alpha NW t ≥ 2.825 at N = 54,
>   the deflated-Sharpe bars, NC1, the placebo, D4, then the holdout's sign) is unchanged and stays pre-registered.
> - **Code check.** `gate0_analysis.py --self-test` (15 survivors posing as dead) gives b_B / b_A 1.047, CI (1)
>   0.873–1.297. That is the expected answer with no survivorship by construction, so the test can see a null.



| step | what | rule, stated now |
|---|---|---|
| G0-pull | the team lead runs `results/cef/screens_2026-11-02/run_gate0_pull.sh`: the CRSP dead population and a CRSP mutual-fund NAV probe (§11) | the manifest's row counts and dates are recorded; `check_holdout` must pass |
| G0-NAV | a NAV for every pulled fund. CRSP-MF where the probe matches (each match reviewed by name). Otherwise the funds' N-CSR / N-CSRS period-end NAVs from EDGAR, read with `scripts/events/cef_corp_action_census.py::nav_beside_price` (the team lead's EDGAR run) | **HALT** (team lead rules) if under 80% of dead five-family fund-half-years 2005–22 get a NAV |
| G0-family | each pulled CEF permno is assigned to one of C4's five families or to "out" (credit, muni, global, convertible, other). The script proposes from name keywords; every row is ruled in `gate0_family_rulings_<date>.csv` | **HALT** if unruled rows exceed 10% of fund-half-years; unruled rows are excluded and counted |
| G0-run | the level statistic at semiannual frequency, with one NAV source for everyone. At each half-year's period-end NAV: the pooled within-family slope of the forward CRSP total return over t+2 .. t+127, delisting returns included, on the within-family discount level. z is not included (there is no daily NAV for the dead). Standard errors clustered by half-year. **A** = the 65 fit funds alone; **B** = every five-family CEF, alive or dead (the 60 left-out live funds included) | **PASS** if b_B < 0 and b_B / b_A ≥ 0.5. **HALT** (team lead rules) if 0 < b_B / b_A < 0.5. **FAIL → withdraw, no trial spent** if b_B ≥ 0. **HALT** also if b_A ≥ 0, because then the frequency change broke the test, not survivorship |

> **2026-11-02 (later): Gate 0, pull 1 is NOT enough; pull 2 is written.** The team lead ran `run_gate0_pull.sh`
> (manifest 2026-11-03T03:01Z: 1,003 CEF permnos; dsf 2,902,916 rows, 2004-01-02..2022-12-30; 36 CRSP-MF NAV matches).
> Measured by `gate0_coverage.py` (output `gate0_coverage_output.txt`), zero trials, no Gate 0 statistic formed:
> - **0 of 36 matches are on CUSIP. 34 are recycled tickers** (ETFs that took a dead CEF's ticker). Only **2 are
>   genuine**: First Trust Value Line Dividend and Value Line 100, CEFs that later became ETFs. Both are dead C4
>   candidates, with **9 fund-half-years** in the fit window.
> - The dead set: 498 CEFs died in 2005–22. **190 are C4 candidates or unclassified** by name (75 + 115):
>   2,626 fund-half-years, against the survivors' 1,570.
> - **Power.** The survivors' semiannual slope is b_A −27.24bp/pp (t −4.55). With pull 1's NAVs, B ≈ A, so
>   **P(flag | halving) = 0.00** whatever the truth. With full EDGAR coverage, under the rule as stated
>   (flag below 0.5): P(flag | halving) = **0.50** at any sample size, because a halving sits on the boundary;
>   0.99 at r = 0.25; 1.00 at r = 0; 0.00 false alarms at r = 1. At 80% coverage the figures are 0.35 / 0.95 / 1.00.
> - **Pull 2:** `run_gate0_ncsr.sh` → `gate0_pull_ncsr.py`, the funds' N-CSR/N-CSRS period-end NAVs from EDGAR.
>   `--plan` on the census's cached index: 133 of 190 candidates map to a filer (57 for rulings); 1,630 filings
>   2008-01..2023-06, plus the 2004–07 quarters.
>
> **Amendment proposal A1, for the team lead** *(superseded 2026-11-02 by the ruling above: both thresholds are now reported reference points; neither is mechanical)*. **It changes no rule until ruled, and it is made before any dead-fund
> NAV has been read:**
> - (i) **Flag below 0.75, not 0.5.** Full coverage: P(flag | halving) 0.97, false alarms at r = 1 0.03. At 80%:
>   0.94 / 0.03.
> - (ii) **Live funds use the families panel's NAV on the same period-end; dead funds use the report NAV.**
>   Pre-condition: on `ncsr_calibration.parquet` (up to 40 survivors), the report NAV and the panel NAV agree
>   within 1% on ≥ 95% of rows. Else HALT. This replaces "one NAV source for everyone", which would need N-CSRs
>   for about 125 live funds as well.

> **2026-11-03: GATE 0 EVIDENCE (post-data; for the team lead's judgment, NOT a pre-registered pass).** Pull 2 ran
> 2026-11-03T03:59Z (`ncsr_manifest.json`):
> - 2,380 filings read: 1,795 NAVs, for 148 of 190 dead candidates;
> - misses: "CRSP close not found beside a NAV" 516, period outside the fund's life 61, no CRSP close 8;
> - 36 candidates had no CIK mapped.
>
> All figures are [V] from `gate0_analysis.py`, `gate0_missingness.py` and `gate0_stress.py` (their `_output.txt`),
> fit only.
>
> **Coverage.** 0.642 of candidate fund-half-years. That **fails the 80% reference** in the table below, which
> would have been a HALT for a ruling before 2026-11-02 and is now an input to the judgment. Calibration: the
> report NAV is within 1% of the panel NAV on 24 of 24 survivor reports.
>
> **Is the loss random?**
> - **At report level, yes.** P(missed) is *lower* near death: 14.1% within 6 months of delisting against 27.8%
>   beyond 5 years, and 13.3% on the last report. Missed and found reports have the same forward CRSP excess
>   return (−22bp, t −0.34) and trailing return (t −0.23).
> - **At fund level, no.** The 42 never-covered funds earned −1,535bp against covered dead funds in their last
>   year (t −2.70). They are the worst dying funds.
> - **The stress bound.** Their last two half-years are imputed at the covered dead funds' 5th-percentile
>   demeaned level (−8.63pp), with their measured returns. b_B/b_A is still **1.031** (1.156 at the 25th
>   percentile).
> - **The cheap parser fix recovers little.** Prior-session closes or ±$0.01 recover 79 of 516 reports, about
>   +1.5% coverage.
>
> **The slopes** (primary cells, family × period-end month; bp per pp; half-year-clustered t):
> - b_A −27.35 (t −4.96), on 1,728 fund-half-years in 65 funds;
> - **b_D −37.19 (t −6.48)**, on 1,478 in 133 funds;
> - b_B −32.90 (t −7.55).
>
> **The ratios, with two bootstraps:**
> - **b_D/b_A 1.360**: 95% CI 0.799–2.127 by fund-half-year, 0.946–2.321 by calendar half-year;
> - **b_B/b_A 1.203**: 0.955–1.542 by fund-half-year, 0.998–1.661 by calendar half-year.
>
> **Sign test:** the dead-only slope is negative in **30 of 33** half-years (binomial p < 0.001), and
> P(b_D ≥ 0) is 0.000.
>
> **Both reference rules are MET**, at the point estimate and at the fund-half-year CI's lower bound:
> - ≥ 0.5: power P(flag | halving) 0.12 at this sample, false alarm 0.00;
> - ≥ 0.75: power 0.89, false alarm 0.01.
>
> **Sensitivities:**
> - with unclassified names excluded: b_B/b_A 1.134 (CI 0.924–1.439);
> - on half-year cells: 1.371 (CI 1.083–1.880).
>
> **Reading.** The dead funds show the effect at least as strongly as the survivors, so survivorship does not
> explain it. If anything, the survivor-only fit understates it. **Recommendation: proceed to approval.**
> The coverage shortfall is real and sits in the worst dying funds, but even an adverse imputation leaves the
> ratio above 1. Mapping the 36 unmapped names by ruling is the only fix that addresses the fund-level gap; it is
> optional, and not needed for this judgment.
>
> **The team lead's call is to be recorded in `docs/SYSTEM.md` §5, dated and labelled "post-data".** It is not
> recorded here, and the counter does not move until the approval commit.
>
> Reproduced 2026-11-03 by an independent re-run (byte-identical output).

**The data gates, after approval** (the C4 trial's own machinery, `require_stage0_rulings` in
`scripts/cef/data_guards.py`):

| gate | test | halts if |
|---|---|---|
| DG-L2 second source | the fit's level book on CRSP primary vs the yfinance leg | gross SR differs by more than 0.2, unexplained |
| DG-L3 data | the 242 fit name-days with \|price TR − NAV TR\| > 10% are triaged; C4's split, bar and seed rulings applied | any flag without a ruling |
| DG-L4 identity | the key absent reproduces C4's v4 book, and the trial script's blend reproduces the sleeve's | any diff |

---

## 5. What we expect [model, U]

- **Fit, already seen.** Unit-risk blend Sharpe about 1.55 against z alone 1.18, uncapped. Under the cap the
  held gross falls to 0.68 of its uncapped level, against 0.74 for z alone, at v4 (0.67 and 0.73 at ×1.27).
- **Account return.** Scaling each book's Sharpe by its cap ratio, at C4's 7.56% ex-ante vol (0.06 × 1.26,
  v4), gives **+1.37%/yr on C4's $100k** (+1.36% at v3's 7.62%; rounded, +1.4% either way). That is **+0.7%/yr on all capital** ($200k across the two accounts,
  `docs/SYSTEM.md`). **Range +0.4 to +1.0%/yr** for out-of-sample shrink.
- **Holdout** (3.74 years). The level book's gross SR 0.5–1.1: P(SR > 0) 0.86–0.99, but P(t ≥ 2.825 on the
  holdout alone) only 0.04–0.26. That is why the judging structure is the C4 precedent (open question 2).
- **P(pass) overall about 0.5–0.7 [U].** Gate 0 is the largest unknown: P ≈ 0.6–0.8, guessed and not measured.
  The fit stage is ≈ 0.9, an in-sample upper bound, and the holdout sign ≈ 0.9.

## 6. What the trial can show, and what would falsify it

### 6.1 The claim

**H-L:** inside C4's families, the discount level against family peers predicts returns beyond C4's z, through
the discount and not the NAV, and survives survivorship. It is recorded as PRESENT, ABSENT or INCONCLUSIVE beside
its D-code (team lead 2026-10-27).

### 6.2 The pass rule, at the CEF bar for N = 54

**This rule is unchanged by the 2026-11-02 Gate 0 ruling and stays pre-registered.** The bar is √(2 ln 54) = **2.825**. The registry's least N for CEF is 54 (`minimum_declared_n`, measured
2026-11-02). Each kill is read once, in order:

1. **Gate 0 and the data gates** (§4b).
2. **P1, fit, the bar.** Regress the daily P&L of the level-only spec book (w_L with its own scalar, × m =
   C4's spec `sizing_multiplier`, read at run time from `ops/specs/c4_families.frozen.json`, never a literal;
   band; cap `max_gross_stress` / m) on the daily P&L of the z-only spec book, which is C4's spec without
   `level_signal`. *Note:* at `release-20261103-1`, `scripts/cef/spec.py` reads only the core's spec. The trial
   script reads C4's the way `scripts/cef/c4_paper_benchmark.py` does (its `SPEC_PATH`), or through `spec.py` once
   that module carries a C4 reader. The alpha's NW t (automatic lag,
   `w4_artifacts.nw_auto_lag`) must be **≥ 2.825**. Else **KILL (D1)**.
3. **P2, fit.** The blended book passes both deflated-Sharpe bars:
   `python3 -m scripts.research.registry bars CEF 54 blend --declared-n 54`. Else KILL.
4. **K1–K3, fit.** Each failure is a KILL with its D-code:
   - NC1: the NAV-leg slope has |t| < 2, else D1;
   - the placebo: the real book ranks above ≥ 19 of 20 within-family shuffles;
   - D4: alpha t ≥ 3.0 with every |β| ≤ 0.10 on C4's factor set (`c4_families.fit`'s D4 block), else D4.
5. **P3, fit, H2.** The blend's gross Sharpe must exceed the z-only book's at matched turnover. `sharpe_diff`
   (`scripts/research/resampling.py`) is reported, not gated: its expected t is about 2.3. Else KILL.
6. **Holdout, opened once.** The level book's gross SR > 0 **and** the blend's gross return above the z-only
   book's. Else **KILL (D3)**.
7. **Net, reported.** At 15bp the blend's net SR must be ≥ the z-only book's; if not, the label is **D2**. It
   does not block paper (C4 is paper only by ruling).

### 6.3 The live stops (per C4 account, on Alpaca's end-of-day history, the P&L of record)

Every threshold is re-measured on the read date by the trial script on the blended book (H14). None is written
in the spec.

| stop | rule | action |
|---|---|---|
| C4 kill rule, **rebuilt on the blended spec book** | HALT on a fidelity break. REVERSE at 120 armed sessions below the 5th percentile of the blended spec book's 120-session price-only returns (stationary bootstrap, mean block 21). REVERSE on a drawdown past its fit worst | as today's rule |
| trial-53 stops R1–R3, rebuilt on the blended book | as `PREREG_VOLTARGET_2026-10-30.md` §6.2 | revert the multiplier |
| **L1, the level component** | at 120 armed sessions, the level-only book's **modelled** P&L on the live panel, decided as the runner decided, below the 5th percentile of its fit 120-session distribution. Modelled, so it is a stop, not evidence | **revert `level_signal`** |
| reported, no rule | the share of sessions at the spec's cap, against the fit's share re-measured on the read date (28.3% at v4) | — |

---

## 7. Divergences from the backtest, stated up front

1. **Paper pays no distributions and fills at the quote**, 8 to 2 minutes before the close (`late_market`).
   The level book's price-only Sharpe on the fit (1.19) is above total return (1.12), so paper does not flatter
   it.
2. **Shorts Alpaca will not lend are skipped.** The level book's shorts are the premium funds (on the fit: DNP,
   GCV, GGN, RFI, BME, ASG), the most likely to become hard to borrow. A skipped short tilts the book long.
3. Whole shares, `min_trade_usd`, and the dust filter on unit weights.
4. **The daily level through the band is not the screen's monthly book.** The fit stage measures the former.
5. **The 9 non-NYSE funds** are scored as gaps, as for C4 today.
6. **The missing-NAV hold and the stale-NAV gate** (report mode) are not in the backtest.

## 8. Costs

**Gross decides on paper.** Turnover falls under the blend (32.9 against 48.5 turns a year at v4's ×1.26; 33.2 against 48.9 at ×1.27; §3.3), so
the drag at any cost is lower than z alone's. **Borrow on the premium-fund shorts is unmeasured.** It is the
arbitrage cost the mechanism relies on, so it must be measured, not modelled, before any real-money proposal.
Real money stays gated as for C4 (paper only, 2026-10-19).

## 9. The revert and the trial count

- **Revert:** delete `level_signal`. C4 is then v4 byte for byte (test 1). A revert is a spec change through
  `/spec-change`, recorded in the stop's row.
- **The trial:** CEF 53 → 54 in the commit that records the approval, not before. The bar at N = 54 is 2.825.
  If Gate 0 runs first as recommended and fails, there is no approval and no trial.

## 10. Open questions for the team lead, each with a recommended answer

1. **Run Gate 0 before the approval commit?** **Yes.** It reads fit data only, like the screen, so a failure
   spends no trial. *Ruled 2026-11-02: Gate 0 is the team lead's post-data judgment (§4b).*
2. **Judging structure:** the fit at the bar, then the holdout's sign (C4's precedent), or the holdout alone at
   2.825? **The C4 precedent.** The holdout alone has P(pass) 0.04–0.26.
3. **The split:** **0.50**, derived (§3.1).
4. **The cap:** **keep 1.90.** It is a margin rule; the blend binds on 28.3% of sessions against 21.5% at v4 (29.0% / 22.0% at ×1.27). Re-derive
   only if the margin rule changes.
5. **Gate 0's pulls:** **the team lead runs `run_gate0_pull.sh`** (CRSP via R2), then the EDGAR N-CSR NAV fetch
   if the mutual-fund probe finds no CEF NAVs.
6. **The fit's return source:** **CRSP primary** (C4's fit), with the yfinance leg as the second source (DG-L2).
7. **Borrow:** **ignored in the verdict, in its own column,** as C4. Measured before any real-money proposal.
8. **Gate 0's sample B:** **every five-family CEF, alive or dead,** the 60 non-shortable live funds included;
   survivorship is about the population, not the tradable list.
9. **Where the final file lives:** **move it to `results/cef/PREREG_C4_LEVEL_2026-11-02.md`** in the approval
   commit, with this folder's draft path left as a one-line pointer.
10. **Amendment A1 (§4b, 2026-11-02 later): flag below 0.75, and live funds on panel NAV with a calibration
    pre-condition?** **Superseded by the ruling** ("keep it flexible and make judgment off results"): both thresholds
    are reported with their power and false-alarm rates, and the team lead judges. Live funds use the panel NAV; the
    calibration agreement is reported.

## 11. Reproduce

```bash
python3 -B results/cef/screens_2026-11-02/alpha_level.py              # the screen (S5)
python3 -B results/cef/screens_2026-11-02/alpha_level_checks.py       # K1-K8
python3 -B results/cef/screens_2026-11-02/prereg_c4_level_design.py   # §3 at C4's v4 spec (release-20261103-1)
python3 -B results/cef/screens_2026-11-02/prereg_c4_level_design.py --spec-ref c4-rel   # the first run, v3
python3 -B results/cef/screens_2026-11-02/gate0_pull_crsp.py --self-test   # Gate 0's SQL on synthetic tables
python3 -B results/cef/screens_2026-11-02/gate0_pull_crsp.py --dry-run     # Gate 0's SQL, printed; no connection
QUANTT_ENV_FILE=<abs path> results/cef/screens_2026-11-02/run_gate0_pull.sh   # the team lead: the pull
```

**Panels:** C4's families panels (`data/cef_families/`, last date 2026-10-09), read only to 2022-12-30. **Code:**
this branch at the commit that adds this file. C4's spec is read from `release-20261103-1` (`c4_families.v4.20261102`, identical on `main` at f27ef81).
The first run read `c4-rel` 8b14298 (`c4_families.v3.20261102`).
