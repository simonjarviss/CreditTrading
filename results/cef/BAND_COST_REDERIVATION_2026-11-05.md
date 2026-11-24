# The no-trade band re-derived from the measured execution cost (core and C4): keep 4.8%

**Status: CLOSED at zero trials (team lead, 2026-11-05). CEF stays 55.** Both books keep `band_width`
0.048. No spec, book json or live-path code changed.

- **History.** Written on 2026-11-05 as a draft pre-registration (`PREREG_DRAFT_BAND_COST_2026-11-05.md`,
  PR #61), at the team lead's ruling of that morning: "pre-register a re-derivation of the rebalancing
  band using the measured execution cost". The team lead accepted its recommendations the same day
  (the Ruling below). It is kept here as a recorded result.
- **The analysis is unchanged.** §1 and §4–§9 describe a trial that was **not run**. They stay as the
  record of what adopting the change would have meant, and what it would have been judged on.

## Ruling (team lead, 2026-11-05; relayed by the coordinating session)

| question | the team lead's answer | what it means |
|---|---|---|
| this note's Q1–Q4: adopt the re-derived band? | **"Accept: keep 4.8%, close"** | **keep 4.8% on both books** (core `cef_discount.v9.20261102`, C4 `c4_families.v5.20261103`); zero trials, CEF stays 55; a CLOSED row in `docs/RESEARCH_STATE.md` |
| | | **re-measure C4's band on its own fill cost after 21 sessions, no earlier than 2026-12-03** (§11) |
| | | **re-derive on a measured live auction impact before any real capital** (§10) |
| the execution study's candidate 1, post-then-cross on paper (`results/cef/EXEC_COST_STUDY_2026-11-05.md`, PR #58, main `1f44bbf`) | **"Not now"** | not built; **re-test after 60+ sessions of fills** |

- **No pass rule now applies.** §4's pass rule is kept as the record and labelled "not run".
- **The 2023+ window §4 would have opened once was not opened.**

- **Analysis:** `results/cef/band_cost_2026-11-05/band_cost.py` (fit only; panels cut at 2022-12-30
  outside the repository before anything is computed). Output of record:
  `band_cost_2026-11-05.{json,txt}` beside it, run at commit `d06ed06`.
- **Second method:** `crosscheck.py` in the same folder, `crosscheck_2026-11-05.txt`: **ALL PASS**
  (§3.6). **Independent review** of the code and of this note's first version: §3.8, every finding
  applied.
- **Provenance.** Every figure tagged [V] was produced by those two scripts on 2026-11-05. [S] figures
  are copied from the file named beside them. **The cost inputs are [S]:** they are read by the script
  from the execution-cost study's aggregates at commit `2476a16` (branch `exec-cost-study`, PR #58),
  `results/cef/EXEC_COST_STUDY_2026-11-05.md`. **PR #58 merged to main as `1f44bbf` on 2026-11-05.** The
  study note and `aggregates_2026-11-05.json` are byte-identical at `2476a16` and `1f44bbf` (`git diff`,
  empty), so every cost figure here holds at main's commit.
- **Panels.** Core: `data/cef/` prices to 2026-10-15 and NAV to 2026-10-14, distributions fetched
  2026-09-11; only rows to 2022-12-30 are read. C4: `data/cef_families/` and trial 52's CRSP extract
  (sha-checked), rows to 2022-12-30. **No 2023+ return, target or turnover was computed here.**

---

## 0. The answer in one table

*As drafted. The recommendations in the last four rows were accepted (the Ruling above).*

| question | answer |
|---|---|
| the core's derived width, at the measured paper cost (7.14bp) | **4.55%** (unit weights, the spec key's units); **0.045** as the spec would hold it. The cost's 95% interval gives 3.41–5.72% (2.72–5.52% centred on 7.14bp). Live: 4.8% [V] |
| C4's derived width, at the core's cost × C4's spread ratio (12.43bp) | **4.07%** (0.040 as written); interval 3.05–5.12%. Live: 4.8% [V] |
| does the core's land on the fit plateau? | **Not by point estimate; yes by the paired test.** At 7.14bp the fit's net Sharpe keeps rising as the band narrows, to the grid's edge (1.6%, +0.085 over h\*). That gap is not significant (HAC p 0.20). h\* against the live 4.8%: **+0.008 Sharpe, SE 0.008** [V] |
| does C4's? | **The same: not by point estimate; yes by the paired test** (6.4% − h\*, HAC p 0.14). Its point estimates lean the other way from the core's: wider in 2010-14, 2015-19 and 2020-22, narrower in 2005-09. **Against the live 4.8% the derived width is worse:** −0.058 Sharpe, HAC p 0.038 on total return, unadjusted and one of about a dozen tests; −0.038, p 0.15 on price only, the paper basis [V] |
| expected turnover and cost (model) | **No saving: the derived widths trade more.** Core at 0.045: +3.3% turnover on the fit; scaled to the live 62–66 turns/yr, about +2.0–2.2 turns/yr and **+0.15% of NAV/yr** at 7.14bp [U]. Net on the fit calendar +0.04pp/yr [V]. C4 at 0.040: +14.3% turnover, **+0.9% of NAV/yr** at 12.43bp, net −0.43pp/yr on the fit [V] |
| can the change pass its own bar? | **No.** On the fit's 4,531 sessions the pass rule's statistic, the Newey–West t of the daily net-return difference (0.045 − 0.048), is **1.34** (1.83 at lag 63) against a bar of 2.837. Forward paper cannot see a +0.04pp/yr change |
| **recommendation, the core (Q1)** | **Do not adopt; record the re-derivation at zero trials.** The live 4.8% is inside the derived interval at the measured cost |
| **recommendation, paper vs live cost (Q2)** | **Keep one band, 4.8%, on paper; re-derive before any real capital from a measured live auction impact,** as part of the real-money cost re-run. Not a grid-midpoint band |
| **recommendation, C4 (Q3)** | **Defer.** Re-measure C4's own fill cost after 21 sessions (no earlier than 2026-12-03); decide no earlier than its 60-session reads (2027-02-01), and only once the law passes its plateau check on C4 |
| **wait for trial 53's 60-session review? (Q4)** | **Yes,** if anything is adopted at all: not before 2027-02-01 (trial 53's R3 at 60 armed sessions on v9) and after the core's 60-session kill-rule review (about 2026-12-22) [U: NYSE sessions counted; a missed session moves both later] |

---

## 1. What would have changed (NOT ADOPTED: the team lead kept 4.8%, 2026-11-05)

| book | key | file | old → new | spec id |
|---|---|---|---|---|
| core | `band_width` | `ops/specs/cef_discount.frozen.json` | **0.048 → 0.045** | `cef_discount.v9.20261102` → `cef_discount.v10.<date>` |
| C4 | `band_width` | `ops/specs/c4_families.frozen.json` | **unchanged, 0.048** (deferred, §11) | unchanged |

- **Mechanics, through `/spec-change`.** Tag `spec-cef_discount.v9.20261102` on the commit before the
  change and push it. Bump `spec_id` and set `_supersedes`. Rewrite `_band_width_note` to the standard of
  the current one: the derivation and its inputs, **the values not chosen** (§3.4: the grid argmax 1.6%,
  the account-weight reading 4.17%), the consequence accepted, what reads the key, and the revert.
- **No code changes.** The key exists and is read by `src/deploy/sleeves/cef_discount.py`
  (`_band_width`) and `scripts/cef/spec.py`. A value change needs no no-op proof. It does need the
  procedure's after-steps: `python3 -m pytest`, `python3 -m ops.doc_audit --check`,
  `python3 -m ops.orient --no-tests`. The sleeve is then built on the new spec for the last panel dates,
  and its targets are read before anything trades.
- **The band still acts on held / m** against the unit target (`_sizing_multiplier_note`), so 0.045 is
  4.5% in unit weights and 5.85% of NAV at ×1.30, as 0.048 is 6.24% today.
- **REVERT:** set `band_width` back to 0.048, or
  `git show spec-cef_discount.v9.20261102:ops/specs/cef_discount.frozen.json`.
- **Not in this PR.** Nothing under `ops/specs` or `ops/books` is touched until the team lead rules.

---

## 2. Why, mechanically

Under a proportional cost the optimal policy is a no-trade band whose width scales as cost^(1/3)
(Constantinides 1986; Davis and Norman 1990; `docs/REFERENCES.md` §6 [S]). The 2026-09-06 width was
derived at an **assumed** 15–22bp. The paper book's cost is now **measured**: 7.14bp per unit of
notional traded against the official close, mostly the quoted half-spread (5.98bp). That is a third to a
half of the assumed figure, so the law moves the band in. At the 2026-09-06 inputs it would give 3.33%
(the study's "about 3.3%").

Re-measuring σ_w and κ_w on today's book pushes the other way:
- the core is 13 names, not 17, and trades on far fewer names a session, so each target weight is
  larger and moves more (mean |w| 0.167 on active name-days);
- since the live book flattens on thin sessions, its dynamics are measured on the sessions where it
  trades.

**The two effects nearly cancel: 4.55%.**

---

## 3. How the width was DERIVED

### 3.1 The cost inputs [S, read by the script from `2476a16`; identical on main at `1f44bbf`]

| input | value | source in the aggregates JSON |
|---|---|---|
| core c\* (paper B, fill vs the official close, notional-weighted) | **7.14bp** (142 orders, 21 `late_market` days) | `tables["all (core, late_market)"].B_bp` |
| its 95% interval (day mean 8.62 ± 2.086 × 8.62 / 3.20, the study's arithmetic) | **3.00–14.24bp** | `B_day_mean_bp`, `B_day_t` |
| the same half-width centred on the pooled c\* (the review's point: the study's interval is centred on the day mean) | 1.52–12.76bp | arithmetic |
| quoted half-spread at 15:52 ET, mean over name-days, 21 sessions | core 13 names **6.06bp**; C4's 15 traded names **10.55bp** | `spread_profile[...].half_spread_bp_mean["15:52:00"]` |
| **C4 c** = core c × 10.55 / 6.06 (ratio **1.741**) | **12.43bp** | arithmetic |
| C4 c at the median ratio (7.54 / 5.04 = 1.496) | 10.68bp (sensitivity) | `half_spread_bp_median` |
| C4's own fills | ONE session (the opening build): B 0.66bp, QHS 10.51bp. **Not used** | `tables["c4, 2026-11-04 (opening build)"]` |

**What c is, and is not.** On paper the cost is the spread, because paper fills at the quote. A live MOC
order fills at the print. It pays no spread; it pays its own **auction impact, which is unmeasured
(n = 0)**. Our orders were a notional-weighted median of **15.2%** of the closing cross (p90 35.9%)
[S: the study §6]. So c\* is the paper P&L of record's cost and is not a forecast of real-money cost.
§10 handles that.

### 3.2 The target dynamics, re-measured on the fit [V]

Definitions (declared in the script before the committed run):
- **book:** the unit target T, before the band and the cap;
- **active pairs:** (t−1, t) with the book trading on both days (core: neither session thin; C4: neither
  row a hold);
- **name-days:** the name is in the book on both days;
- **σ_w** = the pooled sd of ΔT;
- **φ_w** = the pooled AR(1) through the origin; κ_w = −ln φ_w.

| book | σ_w /day | φ_w | κ_w | half-life | active pairs | name-days | window |
|---|---:|---:|---:|---:|---:|---:|---|
| **core** (13, flatten) | **0.06134** | **0.95807** | 0.04284 | 16.2d | 1,025 | 6,752 | 2013-06-24 → 2022-12-30 |
| core 2010-14 / 2015-19 / 2020-22 (2005-09: FLAT, no active pair) | 0.0549 / 0.0575 / 0.0673 | 0.9711 / 0.9675 / 0.9404 | | 23.6 / 21.0 / 11.3d | 266 / 345 / 414 | | |
| **C4** (v5 blend, 74, hold) | **0.04880** | **0.93624** | 0.06588 | 10.5d | 4,020 | 46,200 | 2005-02-18 → 2022-12-30 |
| C4 2005-09 / 2010-14 / 2015-19 / 2020-22 | 0.0471 / 0.0523 / 0.0567 / 0.0319 | 0.9308 / 0.9358 / 0.9356 / 0.9469 | | 9.7 / 10.4 / 10.4 / 12.7d | 877 / 1,243 / 1,193 / 707 | | |
| calibration: the 17-name v6 book, fit only | 0.06050 | 0.95246 | 0.04871 | 14.2d | 2,111 | 18,414 | |
| **the 2026-09-06 inputs** (17 names, whole sample to 2026-09) [S] | **0.04083** | **0.95280** | 0.04835 | 14.3d | | | |

- **The core trades on only 1,025 of the fit's 4,530 session pairs.** It is thin (flat) on 3,484 of
  4,531 fit sessions: all but 2 of the sessions before W1 (2013-06-25), and 1,353 of W1's 2,398 [V]. The
  live book has had no thin session since 2023-08-30 on the panel to 2026-10-14 [S: RESEARCH_STATE, TE4
  row].
- **C4's σ_w falls by 44% in 2020-22** against 2015-19. Its derived width there is 3.26%, against
  3.86–4.48% in the earlier eras. Its dynamics are less stable than the core's.

### 3.3 Recorded against ourselves: the 2026-09-06 σ_w is not reproduced

- The script that measured σ_w = 0.04083 is in neither `main` nor tag `pre-clean-slate`. A search of both
  for the figures and for `sigma_w` / `phi_w` found only the notes.
- On the 17-name book over the fit, the definition above **reproduces the original's φ_w and half-life**
  (0.95246 / 14.2d against 0.95280 / 14.3d). **It does not reproduce σ_w** (0.0605 against 0.0408).
- Pooling every name-day of every session, in the book or not and thin or not, gives 0.0314 on the same
  data [V]. That reading counts days on which no target can move and is not a candidate input. The
  original lies between the two.
- The original's window included 2023–26, which this note may not compute.
- **So the 4.8% the book trades was derived from a σ_w this desk can no longer reproduce.**
  - Under today's definition, 15–22bp on the 17-name fit gives 5.53–6.28%, not 4.26–4.85% [V].
  - This is [U] until the original recipe is found. It does not show that 4.8% is wrong: §3.4 shows the
    fit is flat across the region in question at 15bp.

### 3.4 The derived widths, and the plateau

**Derived** [V], h\* = (3cσ_w² / 2κ_w)^(1/3), in unit weights:

| book | at c\* | c's 95% interval | 5bp | 15bp | 30bp | 22bp (2026-09-06 mid) |
|---|---:|---|---:|---:|---:|---:|
| **core** (c\* 7.14bp) | **4.55%** | 3.41–5.72% | 4.04% | 5.83% | 7.34% | 6.62% |
| **C4** (c\* 12.43bp) | **4.07%** | 3.05–5.12% | 3.00% | 4.33% | 5.46% | 4.92% |

The core's sensitivities at c\* all lie in 4.17–4.79%:
- by era: 4.79 / 4.75 / 4.29%;
- name-days non-zero on either day: 4.53%;
- per-name sd: 4.41%;
- the account-weight reading: 4.17%.

C4's lie in 3.26–4.48% (by era 3.86 / 4.25 / 4.48 / 3.26%). At the median spread ratio C4 gives 3.87%,
and at the core's unscaled cost 3.38%.

**The plateau check** [V]. Each book is the one its account trades:
- core: `1.30 × band_gross_capped(T, b, 1.80/1.30, below_min_names="flatten")`, which reproduces trial
  53's implementation B exactly (§3.6);
- C4: `1.26 × band_gross_capped(T_B, b, 1.90/1.26)`, trial 54's v5 blend (§3.6).

They are scored by `scripts/research/harness.evaluate` (shift(2)). Gross is the headline; net at c\* and
the 5/15/30bp grid sit beside it. No borrow is charged. The fit runs 2005-01-03 → 2022-12-30.

**Core, total return** (price only in the JSON; it reads the same way):

| width | gross SR | ann % | turn/yr (×1.30) | net @ c\* 7.14 | net @ 5 | net @ 15 | net @ 30 | flips? |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1.60% (grid argmax at c\*) | 0.781 | 2.79 | 16.9 | **0.444** | 0.545 | 0.072 | −0.637 | YES |
| 2.27% | 0.753 | 2.65 | 15.3 | 0.443 | 0.536 | 0.103 | −0.547 | YES |
| 2.86% | 0.719 | 2.50 | 14.1 | 0.430 | 0.516 | **0.111** | −0.496 | YES |
| 3.61% | 0.655 | 2.27 | 12.8 | 0.391 | 0.470 | 0.101 | −0.453 | YES |
| **4.50% (as the spec would hold it)** | 0.602 | 2.07 | 11.6 | 0.362 | 0.434 | 0.097 | −0.409 | YES |
| **4.55% (h\*)** | 0.599 | 2.05 | 11.5 | 0.360 | 0.431 | 0.096 | −0.407 | YES |
| **4.80% (live)** | 0.586 | 2.00 | 11.2 | 0.352 | 0.422 | 0.094 | −0.397 | YES |
| 5.73% | 0.544 | 1.83 | 10.2 | 0.329 | 0.393 | 0.092 | −0.361 | YES |
| 7.22% | 0.502 | 1.66 | 8.8 | 0.311 | 0.368 | 0.101 | −0.301 | YES |
| 9.10% | 0.417 | 1.36 | 7.5 | 0.253 | 0.303 | 0.073 | **−0.272** | YES |

- **The full-fit calendar includes 3,484 flat sessions,** which depress every Sharpe and turnover equally
  (CLAUDE.md landmine 8). On the 1,045 W1 sessions the book earns on, the live width makes 8.67%/yr at
  Sharpe 1.222, and h\* 8.90% at 1.250. Over W1's 1,066 decision sessions (every trade, re-entries
  included) the live width trades 47.3 turns/yr, h\* 48.6 and 0.045 48.9.
- **Every row flips sign across the grid at 30bp.** That is the live flatten rule's known property
  (`results/backtests/turnover-live-2026-11-02/REPORT.md` answer 3 [S]). No width here avoids it.

**C4, total return (CRSP ret)**:

| width | gross SR | ann % | turn/yr (×1.26) | net @ c\* 12.43 | net @ 5 | net @ 15 | net @ 30 | flips? |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1.60% | 1.890 | 13.68 | 90.5 | 0.335 | 1.265 | 0.014 | −1.862 | YES |
| 3.20% | 1.646 | 11.98 | 66.8 | 0.506 | 1.188 | 0.271 | −1.105 | YES |
| **4.00% (as written)** | 1.536 | 11.15 | 58.1 | 0.541 | 1.136 | 0.335 | −0.866 | YES |
| **4.07% (h\*)** | 1.528 | 11.09 | 57.4 | 0.545 | 1.132 | 0.341 | −0.846 | YES |
| **4.80% (live)** | 1.476 | 10.68 | 50.8 | 0.602 | 1.124 | 0.421 | −0.633 | YES |
| 6.40% (grid argmax at c\*) | 1.334 | 9.74 | 39.4 | **0.664** | 1.065 | 0.525 | −0.283 | YES |
| 8.14% | 1.103 | 8.23 | 30.1 | 0.602 | 0.902 | 0.498 | −0.107 | YES |
| 9.60% | 0.881 | 6.84 | 24.2 | 0.493 | 0.725 | 0.413 | −0.055 | YES |

On price-only returns (the paper P&L basis) the shape is the same: argmax 6.40% at 0.848, h\* 0.786,
live 0.824. At 8.14% and 9.60% net@30 turns positive (0.082, 0.115).

**The reading.** The point estimates were seen in a scratch prototype before P1 and P2 were written into
the script; the paired tests were not. So P1 is descriptive and P2 is the test.

| | core TR | core PR | C4 TR | C4 PR |
|---|---|---|---|---|
| grid argmax of net @ c\* (**NOT chosen**) | 1.60% (the grid's edge) | 1.60% | 6.40% | 6.40% |
| P1: best − h\* (point; ≤ 0.05 = "flat") | +0.084: **outside** | +0.081: outside | +0.119: outside | +0.063: outside |
| **P2: argmax − h\*, paired (HAC p)** | +0.085, SE 0.067 (**p 0.20**) | +0.082 (p 0.19) | +0.120, SE 0.082 (**p 0.14**) | +0.063 (p 0.44) |
| h\* − live 4.8% (HAC p) | **+0.008, SE 0.008** (p 0.32) | +0.008 (p 0.34) | **−0.058, SE 0.028 (p 0.038)** | −0.038 (p 0.15) |
| spec value − live (HAC p) | 4.5%: +0.010, SE 0.010 (p 0.31) | +0.009 (p 0.33) | 4.0%: −0.061, SE 0.030 (p 0.042) | −0.041 (p 0.16) |
| which side of h\* each era's argmax lies | 2005-09 flat; **narrower** in 2010-14, 2015-19, 2020-22 | the same | **narrower** in 2005-09 (2.56%); **wider** in 2010-14, 2015-19, 2020-22 | the same |
| **the pass rule's statistic, spec value − live: NW t of the daily net difference, lag 21 (63)** | **1.34** (1.83); +0.0385pp/yr | 1.38 (1.88) | −1.91 (−1.61); −0.43pp/yr | −1.30 (−1.10) |
| the same on the gross difference | 2.23 | 2.24 | 2.09 | 2.69 |

The p-values are unadjusted, from about a dozen paired tests. Block 21, M 999, seed 20261105
(`scripts/research/resampling.sharpe_diff`).

- **The core.** The law's 4.55% is not distinguishable from the top of the grid (P2). But in every era
  that trades, the fit's net Sharpe at the paper cost rises all the way down to 1.6–2.3%, the grid's
  edge, so the point estimates say the law puts the band too wide for 7.14bp. **h\* and the live 4.8%
  are indistinguishable** (Sharpe-difference HAC p 0.32; net-return NW t 1.30). At 15bp the curve is flat
  from 2.3% to 7.2% (0.092–0.111), and both h\*(15) = 5.83% and the live 4.8% sit on it. That is the
  plateau the 2026-09-06 note read.
- **C4. By the declared test it lands on the plateau too** (P2: HAC p 0.14 TR, 0.44 PR). Its point
  estimates lean the other way from the core's in three of its four eras: wider in 2010-14, 2015-19 and
  2020-22, but narrower in 2005-09, its own first era (argmax 2.56%, where h\* beats live). **Against the
  live 4.8%, at C4's scaled cost, the derived 4.07% is worse:** −0.058 Sharpe at HAC p 0.038 on total
  return, unadjusted and one of about a dozen tests; −0.038 at p 0.15 on price only, the paper's basis.
  The check passes as declared. Nothing in it argues for moving C4 to 4.07%.
- **Narrower bands earn more gross in both books.** The gross difference 0.045 − 0.048 has NW t 2.2 for
  the core and 2.1–2.7 for C4 (0.040 − 0.048). The cost of the extra trading is what the net columns
  weigh.
- **The values not chosen, named as the 2026-09-06 note named 6.4%:** the core's 1.6% and C4's 6.4%.
  Each is the argmax of a swept column. `z_window = 63` was chosen that way and failed out of sample
  within hours (`/graveyard`). The core's argmax is also the grid's edge, so the true one may be
  narrower still; that is a reason not to look for it.
- **What the two books together say about the law.** With κ_w (the target's mean reversion) standing in
  for the penalty on being off target, the law's width sits away from the fit's net optimum in both
  books: too wide for the core in every era that trades, too narrow for C4 in three of four eras. **No
  gap is significant (P2).** The law is a heuristic calibration, not the books' alpha decay. Q8 asks
  whether to replace it before the next re-derivation.

### 3.5 Units: why unit weights and not ×m

- **Both specs apply the band to held / m against the unit target,** so `band_width` is a unit-weight
  quantity.
- **Under mean-variance the multiplier is a change of risk aversion.** Target, deviation penalty and
  cost all scale with m, and the optimal band in unit weights does not move.
- **The κ-for-penalty law is not scale-free.** Fed account weights it gives h ∝ m^(2/3), which is
  m^(−1/3) in unit weights: 4.17% for the core and 3.77% for C4.
- **The original was derived at m = 1, where the two readings agree.** This note takes the
  scale-free one (Q5).

### 3.6 Second method [V: `crosscheck_2026-11-05.txt`, ALL PASS]

1. **Book identity.**
   - The core's ×1.30 flatten book at 4.8% reproduces trial 53's committed W1 while-trading figures exactly:
     Sharpe 1.2216376610874269, 8.672303781395554%/yr TR, and PR Sharpe 1.328073949495297
     (`results/cef/prereg_voltarget/flatten_exact_2026-11-02.json`).
   - C4's ×1.26 v5 book reproduces trial 54's turnover over live sessions exactly, 51.210635997265534/yr
     (`results/cef/prereg_c4_level/activation_measures_2026-11-03.json`).
   - C4's targets pass trial 52's reproduction gate (fit SR 1.216958 TR / 1.359591 PR, to 1e-9).
2. **σ_w and φ_w by a long-format implementation** agree to 1e-12, for both books.
3. **The law's arithmetic.**
   - The 2026-09-06 inputs give that note's 4.26% (15bp) and 4.85% (22bp).
   - h(30)/h(15) = 2^(1/3) exactly.
   - C4's c equals the core's c × the spread ratio.
4. **Net at c\* with the accounting written out by hand** agrees with the harness to 1e-9. Its
   net-series Sharpe difference agrees with `sharpe_diff`'s delta to 1e-6 (ddof 0 against 1).

### 3.7 Graveyard (`/graveyard`, 2026-11-05)

- Nothing in KILLED, WATCH or CLOSED is a band-width re-derivation.
- **The cautionary case is `z_window = 63`:** the argmax of a swept column, chosen with the holdout
  sealed, which failed out of sample (gross 1.75, net −0.298). Hence §3.4 names the argmax and does not
  choose it.
- "Sequential Σ⁻¹α + band" (killed) concerns combining the band with Σ⁻¹ and is not re-opened.
- The execution study's candidate 4, a per-name tick-aware band, is a different trial and is not
  proposed here.
- "OU / per-name κ" (withdrawn) is the reason a per-name κ_w is not used: the live z already carries
  κ^(1/2).

### 3.8 Independent review (quant-reviewer, 2026-11-05), and what changed

**Verdict on the code:** no lookahead, no holdout leak, no unit error, no execution-convention error, no
silent fallback. The reviewer re-ran the definitions in its own scratch scripts and reproduced the core's
σ_w and φ_w to the last digit. Also confirmed:
- the m-handling matches the sleeve (held / m against the unit target, `_cap_gross(·, cap / m)`, × m)
  and trial 53's `flatten_exact.py`;
- c's units match `evaluate`'s one-way turnover;
- C4's hold detector equals `spec_targets`' own thin rule on all 382 rows.

**Findings on the first version of this note, each applied and the analysis re-run:**

| # | finding | disposition |
|---|---|---|
| 1 | The note said C4 "fails its plateau check", but C4 passes the declared test (P2, p 0.14 / 0.44) exactly as the core does | rewritten (§0, §3.4, §11, Q3, Q8). Q3's "defer" stands on the n = 1 cost and the live comparison |
| 2 | The 2005-09 era was omitted; C4 trades in it (877 active pairs), and there its argmax is narrower (2.56%) | `ERAS` now starts at 2005-09; the core's is printed FLAT and never fed to the law |
| 3 | W1 "while-trading" turnover averaged over the earn mask and dropped re-entries after thin stretches (42.2 → 47.3 at live) | counted over decision sessions; §3.4 and §7.1 corrected |
| 4 | The "t ≈ 1.0" was a Sharpe-difference ratio, not a t on the return difference the pass rule names | the statistic is named and printed: NW t of the daily net difference, 1.34 (lag 21), 1.83 (lag 63). Still far below 2.837 |
| 5 | Minor: the core's +0.03pp was h\*'s, not 0.045's (+0.04); a bold −0.300 that was not the column's best; the cost interval is centred on the day mean | corrected; the interval centred on c\* is printed beside it (1.52–12.76bp → 2.72–5.52%) |
| 6 | Off-by-one: C4's first active pair was dropped | `inactive[:first]` in both scripts (σ_w unchanged to 5 dp; φ_w 0.93622 → 0.93624) |

---

## 4. Committed in advance: NOT RUN (kept as the record; Q1 was answered "keep 4.8%")

- **Execution:** shift(2) through `scripts/research/harness.py`; no new backtester.
- **Turnover-matched (H2).**
  - The core's 4.5% and the live 4.8% are an H2 pair: their turnovers differ by 3.3% on the fit, within
    5%. Its matched gross comparison is +0.016 Sharpe (0.602 against 0.586) [V].
  - C4's 4.0% is not an H2 pair (+14.3%), so it is compared at a priced cost.
  - Two widths of one band cannot be matched more closely without becoming the same width.
- **Gross is the headline.** The paper is scored gross (team lead D19/D20, 2026-09-15). The P&L of record
  is Alpaca's end-of-day history (2026-10-19), which already pays paper's fill cost. The 5/15/30bp grid
  sits beside it, labelled, with the sign flip stated: every row flips at 30bp. Borrow is not charged on
  paper and would be its own column.
- **Eras:** 2010-14, 2015-19, 2020-22 on the fit (2005-09 is flat), and 2023+ only as below.
- **The pass rule, at the CEF bar for N = 56.** The claim is that 0.045 earns more net at c\* than 0.048.
  It passes only if:
  - **the statistic:** the Newey–West t (lag 21, one month; lag 63 printed beside it) of the daily
    net-at-c\* return difference, 0.045 − 0.048, on the fit's 4,531 sessions, is at least
    √(2 ln 56) = 2.837; and
  - the sign holds on the window below.
  - **On the fit it is 1.34 on total return and 1.38 on price only (1.83 / 1.88 at lag 63) [V]. The
    trial cannot pass. Its best verdict is INCONCLUSIVE**, and that is known before it starts. Q1 turns
    on this. (The first version of this note quoted the Sharpe-difference ratio, 1.02 / 0.97, as "t";
    the review named the mismatch. Under every statistic it is far below the bar.)
- **The holdout, opened once.** No clean time holdout exists for either book:
  - the core's 2023+ was opened on 2026-07-31 and computed in the v7 pre-registration
    (`docs/RESEARCH_STATE.md`, the Q7 correction of 2026-11-01 [S]);
  - C4's 2023-01-03 → 2026-09-30 was opened on 2026-10-18 (trial 52) and again for the v5 blend on
    2026-11-03 (trial 54) [S];
  - the drafting session read the turnover study's 2023+ turnover by width
    (`results/backtests/turnover-live-2026-11-02/REPORT.md`, "Context only" table, hold book: 59.3 / 53.5
    / 44.7 / 38.0 / 28.5 turns/yr at 2.4 / 3.2 / 4.8 / 6.4 / 9.6%) [S];
  - it did not open that study's `run.log`, which prints 2023+ gross Sharpe by width.

  If approved, the approval commit computes 2023-01-03 → the panel's last date **once**, for 0.045 and
  0.048 only (no grid). It reads only the sign and size of the net-at-c\* difference, labelled
  CONTAMINATED. **It can veto** (negative by more than one SE: keep 0.048). **It cannot pass.**
- **The 27-name set (H9) is not touched.** Returns are computed only on the core's 13 and C4's 74.
- **Negative control (H12), where the width cannot act.** Replay the decide on the same panel at 0.045 and
  0.048. Any name whose |unit target − held / m| is at most 0.045 must get the same order (none) under
  both. The two plans may differ only on names whose gap lies in (0.045, 0.048], or by the band edge's
  0.003. Any other difference is a code fault.
- **We do not re-tune on live data.** The next legitimate change is a re-derivation from a better
  measured cost (§10), never a re-sweep.

### 4b. Stage 0

- **This note reads no new data source.**
  - The core's panels are the live book's, cut to 2022-12-30.
  - C4's are trial 52's, cut the same way, with the CRSP extract sha-checked and the trial's
    reproduction gate passed.
- **No Stage-0 flag table is produced, so there is no rulings file to block on.**
- The window opened in §4 reads the core's live panels, whose distribution panel ended 2026-09-03 when
  the turnover study cut it [S]. That window must cut its returns at the distribution panel's last
  ex-date, per name, and refuse otherwise. This is the turnover study's DIST_END rule and its open F4.

---

## 5. What we expect (a model, fit only)

| | core, 0.045 vs 0.048 | C4, 0.040 vs 0.048 (not proposed) |
|---|---|---|
| fit turnover (×m, calendar) | 11.6 vs 11.2 (+3.3%) | 58.1 vs 50.8 (+14.3%) |
| 2020-22 turnover | 33.0 vs 31.9 (+3.4%) | 39.4 vs 32.9 (+19.7%) |
| scaled to the core's live 62.1–66.3 turns/yr [U] | +2.0–2.2 turns/yr; **+0.15–0.16% NAV/yr** at 7.14bp (about $150 on $100k) | |
| net Sharpe at c\*, fit | +0.010 (SE 0.010) | −0.061 (SE 0.030) |
| net %/yr at c\*, fit / 2020-22 (TR) | +0.04 / +0.11pp | −0.43 / −1.76pp |
| cost at c\*, fit | +0.027% of NAV/yr | +0.90% of NAV/yr |

- **There is no cost saving.** The measured cost is lower than the 2026-09-06 assumption, so the law
  moves the band in. The band trades slightly more and pays slightly more.
- **The gain is the gross the extra trades capture:** +0.065pp/yr over the fit calendar, +0.19pp in
  2020-22 (core, 0.045).
- **Live, a 3% turnover change is invisible.** The turnover study's 24-session windows in 2023+ run from 0
  to 109 turns/yr (p05–p95) [S].

---

## 6. What would have FALSIFIED it (not run)

**No P&L statistic can.** The modelled improvement is +0.04pp/yr net, NW t 1.34 over the whole fit
(1,045 sessions in which the book trades, about 4.1 years of them). At the same information per session,
t grows with √n: about 9 years of trading to reach t 2, and about 19 to reach the bar [U: that scaling,
not a power calculation]. The pre-registration says so rather than invent a falsifier the data
cannot meet. What can be falsified is the implementation and the inputs:

| | statistic | horizon | threshold | action |
|---|---|---|---|---|
| F1 implementation | §4's replay control: order differences outside (0.045, 0.048] | every decide for 20 armed sessions | any | a code fault: halt the activation and revert |
| F2 turnover | realised turnover per traded session against a replay of the same decides at 0.048 | 20 armed sessions | lower than the replay's | a code fault: the narrower band cannot trade less on the same targets |
| F3 the cost input | B re-measured by the execution study's script | at 60 armed sessions after activation | the 95% interval of h\*(B), on §3.2's inputs re-measured that day, excludes 4.5% | revert to 0.048 |
| F4 the law | the §3.4 plateau check re-run at the F3 cost | the same | P2 fails (the argmax beats h\* at HAC p < 0.05) | revert, and Q8 governs the next derivation |

---

## 7. Divergences from the backtest, stated up front

1. **The fit is mostly flat.** The live book is not. The core trades on 1,045 of W1's 2,398 sessions,
   and on every session since 2023-08-30. Its live turnover (62.1–66.3/yr [S]) is about 1.3–1.4 times
   W1's 47.3 over decision sessions. The width's effect was measured in a quieter book.
2. **Band holds are share counts live and weights in the harness.** Held weights drift with prices
   between trades.
3. **Paper fills at the quote at 15:52** (`late_market`), not at the auction. c\* is that fill's cost.
4. **Whole shares; the dust filter** (`min_abs_weight` 0.005 on the unit weight); `min_trade_usd` $0.
5. **The deferred flip.** A long↔short flip trades only its closing leg that session. The harness flips
   instantly (turnover study: −0.75pp/yr in 2023+ on the hold book [S]).
6. **The missing-NAV hold, the stale-NAV gate (report mode), and skipped unshortable shorts.**
7. **Paper pays no distributions, charges no borrow and processes no corporate actions.** The
   corporate-action gate halts instead.
8. **The core's te4 rule** (trial 55, not yet active) would trade reduced books on 4–5-name sessions. Its
   band residues depend on the width (§8).

---

## 8. Interactions with the live trials

| trial | what it reads | does a band change confound it? | so |
|---|---|---|---|
| **53, the vol target** (core ×1.30 on v9 since 2026-11-04; C4 ×1.26) | R1–R3, read on the P&L of record and calibrated on the 4.8% book at ×m (`results/cef/prereg_voltarget/stops.py`). **R3 (realised vol at 60 armed sessions) is H-VT's falsifier**; R2 is read at 120 | **Yes.** The width moves turnover, held gross and so realised vol. A change inside the 60-session window would make an R3 firing unattributable, and its threshold would be re-measured on a book that traded for only part of the window | **wait:** no band change before each account's 60th armed session on its multiplier, 2027-02-01 at the earliest [U] |
| **the core's kill rule** (60 live sessions) | live net Sharpe < 0; slippage > 2× modelled for 5 sessions; spread < 12% | Yes, for (a) and (b): a band change moves the cost the slippage rule compares | wait for that review too, about 2026-12-22 [U] |
| **54, C4-LEVEL** (v5 blend) | L1 (the level book's 120-session modelled P&L) and C4's H11 at 120 sessions, both on `m × band_gross_capped(T, band, 1.90/m)` | Yes: both references are built at the spec's band | C4 is deferred (§11), so nothing moves |
| **55, te4** (approved, not active) | K1–K3, re-measured on the read date by `results/cef/prereg_thin_te4/compose.py` at the read date's band; fit evidence (+2.13pp/yr matched, t 2.34) at 4.8% | **It depends on the width, but its rule survives a change.** compose.py was revised to re-measure at a moved band rather than raise. Its activation already waits for the core's 60-session review | if a band change is ever adopted, re-run compose.py at the new band before te4 activates, and label each te4 episode with the band it traded |

**Should the trial wait for trial 53's review? Yes,** if it runs at all. Waiting costs about nothing,
because the modelled gain is +0.03pp/yr. Not waiting would cost trial 53 its one falsifier.

---

## 9. The live stops (if adopted; not adopted)

- **Unchanged:**
  - the spec's HALVE / KILL lines (report only);
  - the core's 60-session kill rule;
  - trial 53's R1–R3, re-measured on the read date at the read date's band (H14).
- **Added:** F1–F4 (§6), read by the team lead through `/spec-change`, as trial 53's are. No code acts on
  them.
- The F1/F2 replay is a report line, built and tested in the activation release, or the change is not
  activated (te4's precedent, §6.3 of its pre-registration).

---

## 10. The paper-versus-live cost question

The band is derived for a cost. Paper's cost is the spread (7.14bp), a paper-only drag: a live MOC fill
at the print would not pay it. Real money's cost is auction impact, unmeasured, on orders a sixth to a
third of the closing cross. A band derived for paper may be wrong for real money. What the fit says
about each:

| cost | core h\* | core fit at that cost (TR) |
|---|---|---|
| 7.14bp (paper) | 4.55% | net rises as the band narrows, to the grid's edge; h\* ≈ live |
| 5bp (grid) | 4.04% | rises as it narrows |
| 15bp (grid mid) | 5.83% | **flat 2.3–7.2%**; live and h\* both on it |
| 30bp (grid) | 7.34% | rises as it widens (−0.637 at 1.6% against −0.272 at 9.1%) |

**The options:**
- **(a) One band for the paper score now, re-derived before any real capital.**
- **(b) A band at the grid's midpoint (15bp): about 5.8%.** It imports an assumed cost, which is the
  2026-09-06 derivation's weakness. On paper it would cost a little: net at 7.14bp of 0.329 at 5.73%
  against 0.352 at 4.8% (fit, TR).
- **(c) Keep 4.8% for paper and re-derive before real capital: (a) with no change today.**

**Recommended: (c).**
- **4.8% is inside the core's derived interval at the measured paper cost** (3.41–5.72%; 2.72–5.52%
  centred on 7.14bp). It is also
  inside the law's range for 5–15bp of real-money cost (4.04–5.83%), and on the fit's 15bp plateau. One
  band serves both until the live cost is measured.
- **A paper-optimised band would weaken the paper record as evidence.** The paper book exists partly as
  evidence for real capital. Narrowing it for a paper-only spread makes the paper book trade more than a
  real-money book could carry: at 30bp the 1.6% band nets −0.637 against −0.397 at 4.8% on the fit.
- **Real capital is deferred** until Alpaca Canada is approved, at least six months
  (`docs/SYSTEM.md` §5, 2026-10-28 [S]). **The real-money cost re-run is already the gate for any
  capital** (2026-10-09 [S]).
- **So:** the band's re-derivation becomes a named item of that re-run. It uses a measured auction
  impact: the execution study's candidate 2, a pre-registered live impact measurement with a per-order
  cap against the expected cross. It is adopted only if the law passes its plateau check at that cost,
  or if Q8 has replaced the law.

---

## 11. C4: the cost is n = 1

| option | what | for | against |
|---|---|---|---|
| (i) scale the core's cost by the spread ratio | c = 7.14 × 1.741 = **12.43bp** → **4.07%** (0.040). The ratio is the mean quoted half-spread at 15:52 over 21 sessions (C4's 15 traded names, 10.55bp, against the core's 13, 6.06bp), `spread_profile` in the study's aggregates JSON at `2476a16` [S]. At the median ratio (1.496) → 3.87% | available now. The spread is the stable part of the cost (the core's HS day t is 26.7) | **worse than live at that cost** (−0.058 Sharpe, p 0.038 TR, unadjusted; p 0.15 price only), though on the plateau by P2. The fit's point estimates lean wider in three of four eras. The 15 names are one opening build's, not C4's turnover over time. C4's σ_w is unstable by era (3.26–4.48% derived) |
| (ii) **defer** until C4 has N sessions of its own fills | re-measure B and the spread on C4's own orders | no number C4 has not paid | waits |

**Recommended: (ii), defer.**
- **N = 21 armed `late_market` sessions,** the sample the core's 7.14bp rests on: no earlier than
  2026-12-03 [U: NYSE sessions from 2026-11-04].
- **No C4 change before its 60th armed session on ×1.26** (2027-02-01 at the earliest, trial 53's R3).
  Trial 54's L1 and H11 run to 120 sessions (2027-04-28 at the earliest) [U].
- **Adoption needs the re-derived width to be no worse than the live 4.8% at C4's own measured cost**
  on the fit, as well as P2. Today it is worse on total return at that cost.

---

## 12. Open questions for the team lead, each with a recommended answer (Q1–Q3 ruled 2026-11-05 as recommended; Q4 moot; Q5–Q8 open)

| # | question | recommended answer |
|---|---|---|
| **Q1** | Approve the core's 0.048 → 0.045 as CEF trial 56? | **No.** Record the re-derivation at zero trials (a CLOSED row: "measured, adopted nothing, spent no trial"). The change is inside its own error (NW t 1.34), cannot pass the bar (2.837), and cannot be seen live. A trial would raise every later CEF trial's bar from 2.831 to 2.837 and confound trial 53's falsifier |
| **Q2** | The paper-versus-live cost question | **(c):** keep one band, 4.8%, on paper. Make the re-derivation at a measured live auction impact a named item of the real-money cost re-run (§10). Not a grid-midpoint band |
| **Q3** | C4: scale the core's cost by the spread ratio, or defer? | **Defer** (§11): N = 21 sessions of C4's own fills; no change before 2027-02-01; adoption only if the re-derived width is no worse than live at C4's own cost |
| **Q4** | If Q1 is approved anyway: wait for trial 53's 60-session review? | **Yes.** Activate no earlier than 2027-02-01, after R3 is read for the core, after the core's 60-session kill-rule review, and with compose.py re-run for te4 (§8) |
| **Q5** | Derive in unit weights (the key's units, scale-free) or in account weights (×m)? | **Unit weights** (§3.5). The account reading (4.17% core, 3.77% C4) is shown and not used |
| **Q6** | The 2026-09-06 σ_w (0.04083) cannot be reproduced (§3.3). Correct the record? | **Yes.** This note's evidence-log entry (E-2026-11-05-40) records it. The core's `_band_width_note` carries a dated correction at the next `/spec-change` of that key; no spec is edited for a note alone |
| **Q7** | Is the cost interval right to use? | **Yes, as a range, not a point.** The 95% interval is the study's day-clustered one (3.0–14.2bp). B's day sd is about 12bp, so it narrows only slowly (§3 of the study) |
| **Q8** | By point estimate, the law's width sits away from the fit's net optimum in both books, in opposite directions (none significant). Replace κ_w as the penalty before the next re-derivation? | **Yes, as a zero-trial method note before the real-capital re-derivation.** Derive the penalty from the book's own forgone alpha (its IC term structure), check it reproduces the fit's net optimum on both books, and only then use it. Until then, any band re-derivation is labelled heuristic |

---

## 13. Trial accounting

- **CEF stays 55.** Nothing was spent. Q1 was answered as recommended (the Ruling above). The commit
  that records the ruling adds a CLOSED row naming this note and `results/cef/band_cost_2026-11-05/` to
  `docs/RESEARCH_STATE.md`.
- *As drafted, not taken:* had Q1 been approved, CEF would have gone 55 → 56, with the trial's daily P&L
  series stored with `scripts/research/registry.py` and the bar at √(2 ln 56) = 2.837.

## Reproduce

```bash
python3 scripts/cef/c4_paper_benchmark.py stage          # C4's CRSP extract, gitignored, sha-checked
python3 -B results/cef/band_cost_2026-11-05/band_cost.py --data-root <a checkout's data/> \
    --cut-dir <a new folder outside the repository>      # ~1 min
python3 -B results/cef/band_cost_2026-11-05/crosscheck.py --cut-dir <the same folder>
```
