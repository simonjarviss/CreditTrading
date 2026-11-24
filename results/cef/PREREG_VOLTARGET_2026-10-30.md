# Pre-registration: raise the live book's volatility target, core ×1.30 and C4 ×1.26 (CEF trial 53, APPROVED; amendment 1)

Date: drafted 2026-10-30; **APPROVED 2026-11-01 by the team lead** (answered interactively, relayed by
the coordinating session). Counter: **CEF, trial 53**, moved 52 → 53 in the commit that records this
approval (`docs/RESEARCH_STATE.md`, same commit). Author: an agent, for the team lead.
**Amendment 1, APPROVED 2026-11-02 (§0.B):** core ×1.13 → ×1.30, C4 ×1.27 → ×1.26, and the core's stops
recalibrated on the live thin-day rule. It is an amendment, not a new trial; the counter stays at 53.

## 0.B Amendment 1 (APPROVED 2026-11-02, the team lead)

**Approved interactively on 2026-11-02, about 22:00 ET, relayed by the coordinating session.
It is an amendment, NOT a new trial: CEF stays 53.** The hypothesis (H-VT), the rule and the
implementation (`sizing_multiplier`) are unchanged. What changed is one input the rule was fed.

**What changed, and why.**
- §0.A's multipliers were derived on the canonical harness's book, which HOLDS the previous target on
  a thin session (fewer than `min_names` eligible). The live core sleeve FLATTENS there instead
  (`src/deploy/sleeves/cef_discount.py`, the `min_names` block). The thin-days report found this:
  `results/backtests/thin-days-2026-11-03/REPORT.md` §6, branch `research-thin-days`.
- Re-measured on the flatten book: `results/cef/prereg_voltarget/FLATTEN_REMEASURE_2026-11-02.md`,
  PR #35, carried on this branch as 2c67a85 and ef3041e [V there]:
  - **the core is flat on 56% of W1** (1,353 of 2,398 sessions);
  - its unit daily sd is **0.002351** over the calendar and **0.003556 on the sessions it trades**,
    against the hold book's 0.004095;
  - **the 2026-10-29 rule applied literally gives core ×1.96 (C4 ×1.26)**. That figure is inflated:
    the rule's identity m_core / m_c4 = sd_c4 / sd_core counts the flat sessions as zero risk;
  - **on the sessions the core trades, the same rule gives ×1.3007 → 1.30** (C4 1.2642 → 1.26).
- **×1.30 restores the risk the trial approved.** While the book trades, zero-edge P(HALVE) / P(KILL)
  in 12 months are **16.7% / 1.68%**, against the 15.9% / 1.5% approved in §0.A on the hold book.
  ×1.13 carries 10.3% / 0.66% on the live book.
- ×1.30 is inside the plateau: combined Sharpe 1.626 TR / 1.745 PR, within 1.624–1.638 for every core
  multiplier from 0.8 to 2.5.

**The new values.**

| | §0.A (2026-11-01) | **Amendment 1 (2026-11-02)** |
|---|---|---|
| core `sizing_multiplier` | 1.13 (hold book) | **1.30** (flatten book, trading sessions) |
| core spec | `cef_discount.v8.20261101` | **`cef_discount.v9.20261102`** |
| C4 `sizing_multiplier` (before C4 arms) | 1.27 | **1.26** (re-derived 1.2642, rounded down) |
| C4 spec | `c4_families.v3.20261102` | **`c4_families.v4.20261102`** |

**The new stops** (§6.2's R1–R3).
- The core's stops are now **calibrated on the flatten book's trading sessions**: R1 **10.14%**, R2
  **−3.06%**, R3 **12.07%** at ×1.30 [V `stops.py --core-earning-only`].
- C4's stops at ×1.26, on its own book (C4 holds, so it is unaffected): R1 10.04%, R2 −3.02%, R3 9.90%.
- These supersede §0.A's 11.17% / −3.52% / 12.12% (core) and 10.09% / −3.04% / 9.96% (C4). The rules
  and horizons are unchanged.
- H14 still governs: they are re-measured on the read date by
  `stops.py --scratch FLAT --m-core 1.30 --m-c4 1.26 --core-earning-only FLAT/flatten_masks.parquet`.
  FLAT is `flatten_series.py`'s root.
- **Why trading sessions and not every session.** A calibration on every session would fire
  spuriously while the book trades: R3 18.5% of the time at ×1.30, against its 5% design
  (FLATTEN_REMEASURE §4).
- **Nothing in code reads these thresholds.** No runner, orient or ops path acts on R1–R3. They are
  read by the team lead, through `stops.py`, and acted on through `/spec-change` (§6.2).

**Expected, on the fit** (exact implementation B, core account, total return): 3.78%/yr over the
calendar and 8.67%/yr while trading (SR 1.222). Against ×1.13 that is +0.47 and +1.08pp/yr. The
combined book gains +0.21pp/yr (model) [V FLATTEN_REMEASURE §4b]. Worst drawdown is 8.39% (W1), and
9.7 / 18.3 / 39.1% through 2008 over the 5 non-thin year-end books.

**The REVERT.**
- **Core:** set `sizing_multiplier` back to 1.13 (spec v8), or restore it whole with
  `git show spec-cef_discount.v8.20261101:ops/specs/cef_discount.frozen.json`. That tag is local only,
  on the commit before the change.
- **C4:** `git show spec-c4_families.v3.20261102:ops/specs/c4_families.frozen.json` (local).
- Deleting the key on either returns that account to the unit book (§9).

---


## 0.A The approval (2026-11-01, the team lead)

**The approved values are the milder pair, not the draft's.** The team lead chose the 2026-10-29
rule's variant (§3.3): **core ×1.13, C4 ×1.27, at a 5.25% combined target**, not the draft's
×1.24 / ×1.39 at 5.75%. The body below is the draft as approved. Where it says 1.24, 1.39 or 1.41,
read 1.13 and 1.27 for what trades. The figures at the approved values are in the table below. Each
was computed by the same helpers before the approval, apart from the two exact builds, which were run
on 2026-11-01 at the approved values (`impl_core_2026-11-01_m1.13.*`, `impl_c4_2026-11-01_m1.27.*`).

**The values, exactly as the draft's rule computes them** [V `derive.py` §4]:
- the 2026-10-29 rule's term (d) binds at 5.25% on the spec series;
- the per-account multipliers there are **core 1.1357, C4 1.2712** (C4 on its 1.90 spec book);
- written to two decimals and rounded down (the declared rule): **1.13 and 1.27**;
- the effective ex-ante vol targets are core 0.06 × 1.13 = 6.78%, C4 0.06 × 1.27 = 7.62%; combined
  5.25%.

**The answers to §10, as ruled:**

| question | ruling |
|---|---|
| 1. C4's value | **The derived value on C4's spec book.** At the approved rule that is 1.2712 → **1.27** |
| 2. Which declared rule governs | **Answered by the choice of values:** the 2026-10-29 rule (5.25%) governs this book. At ×1.13 / ×1.27 its term (d) holds: mean uncapped gross core 1.36 against 1.80, C4 1.84 against 1.90 [V `risk.py`]. So **no override of term (d) is needed**, and none is recorded. What is recorded (`docs/SYSTEM.md` §5, 2026-11-01) is that the 2026-10-29 rule, not the 2026-10-28 one, sets this book's target |
| 3. The framework's gate on a vol increase (`PORTFOLIO_FRAMEWORK` §2.6) | **Waived for paper only**, recorded in `docs/SYSTEM.md` §5. Never for real money |
| 4. The stops | **R1–R3 as written, acted on by the team lead** through `/spec-change`. The R1 line in the drawdown report (§6.2) is **not built in this pass**: the runner has no fit series to re-measure D_R from. Until it is, the team lead reads `stops.py` |
| 5. Start | **The core at its next release; C4 at its arming,** already at its multiplier, with its H11 reference rebuilt on the raised book |
| 6. Trials | **One trial, CEF 53, N = 53**, bar √(2 ln 53) = 2.818 |
| 7. The documents that call the core's 2023+ "sealed" | **Corrected** with dated notes in `docs/RESEARCH_STATE.md` and `PORTFOLIO_FRAMEWORK_2026-10-15.md` §9, and recorded in `docs/SYSTEM.md` §5, 2026-11-01 |

**What the approved book expects, and the stops at the approved values** [V `risk.py` book
"rule-2026-10-29"; `impl_core.py --m 1.13`, `impl_c4.py --m 1.27`; fit only]:

| | value |
|---|---|
| gross, fit path, combined | **8.50%/yr total return, 9.18% price only**, Sharpe 1.681 / 1.756 (model). Exact implementation: 8.76% / 9.65% (mean of the accounts) |
| core account, exact B | 6.66% TR (SR 0.923) / 7.25% PR (0.974); vol 7.22%; maxDD 14.84% TR; held at the cap on 19.5% of sessions (today 7.3%) |
| C4 account, exact B | own window 9.17% TR (SR 1.272) / 10.57% PR (1.409); vol 7.21%; maxDD 10.57% TR; held at the cap on 22.1% of sessions (26.9% on 2013–22) |
| P(HALVE), 12 months, zero edge, through 2008 (min / median / max over the 10 core books) | combined **1.6 / 3.4 / 11.7%**; core account **7.2 / 15.2 / 51.4%**; C4 account **16.3%** |
| P(KILL), same | combined **0.00 / 0.08 / 0.92%**; core account **0.35 / 2.4 / 17.4%**; C4 account **1.6%** |
| worst drawdown | core account W1 14.05% model / 14.84% exact; through 2008 14.8 / 22.5 / 36.4%; C4 10.8%; combined through 2008 6.8 / 7.9 / 15.6% |
| costs (model, TR) | combined net **+6.63 / +2.88 / −2.73 %/yr** at 5 / 15 / 30bp, breakeven 22.7bp; C4 account 16.9bp. The sign flips between 15 and 30bp. Gross decides; real money is gated separately (§8) |
| R1 (superseded by §0.B) | core **D_R 11.17%**; C4 **10.09%** (drafting-day values; `stops.py --m-core 1.13 --m-c4 1.27` re-measures on the read date) |
| R2 | core **−3.52%**; C4 **−3.04%** (120 armed sessions) |
| R3 | core **12.12%**; C4 **9.96%** (60 armed sessions) |

**Implementation** (§1, unchanged by the approval): the frozen key `sizing_multiplier`, absent =
today. The core's value is set in `ops/specs/cef_discount.frozen.json` as the activation commit, after
the code. C4's value goes into C4's spec on `c4-integrate` at its arming. The edit is written out in
that activation commit's message, and is not applied to that branch here.

---

**Labels.**
- **[V]** computed in this session by the helper named, in `results/cef/prereg_voltarget/`. Fit
  window only: every frame ends by 2022-12-30, asserted.
- **[doc: path]** copied from a note and not re-run. `SCRATCH/...` is the session scratch folder that
  holds the 2026-10-28 allocation note (`alloc/NOTE.md`), its independent review (`alloc_review/`) and
  the 2026-10-29 four-sleeve note (`alloc4/NOTE.md`). None of these is in the repository.
- **[U]** arithmetic on a stated assumption.

**The ruling this implements** (team lead, 2026-10-29/30, relayed in the drafting brief; not yet in
`docs/SYSTEM.md` §5):
- optimise the percentage return on ALL capital, the real-money view;
- the book is the core 13 in its own account plus C4 (74 non-credit CEFs) in the spare account;
- the ex-date short and PCEF stay built but OFF;
- each account is sized at its per-account equal-risk multiplier from the allocation review: core
  ×1.24 and C4 ×1.41, at a 5.75% combined target;
- this changes the core's live vol target, so it is a pre-registered CEF trial, through `/spec-change`.

**The declaration** (`prereg_voltarget/declared_2026-10-30.json`, 2026-10-30T19:03:07Z) was written
before any number in this folder was computed. It fixed the implementation choice, the rounding rule,
the plateau test, the risk statistics and the stops. It also lists the prior numbers I had already seen.

---

## 0. The draft's answer in one table (its values are superseded by §0.A)

| item | answer |
|---|---|
| **implementation** (§1) | **A new optional frozen key, `sizing_multiplier`**, in each cef_discount-type spec. Absent, the book is today's, byte for byte. Present as m, the sleeve builds its unit book exactly as today, with `vol_target_annual` unchanged at 0.06, and holds m times that book under the account's own gross cap. C4's fidelity gate, the core's no-op proof and the missing-NAV hold all survive. Changing `vol_target_annual` was not chosen |
| **values** (§3) | **core 1.24; C4 1.39** (1.41 as ruled). Both come from the 2026-10-28 declared rule: W6's form, σ_margin binding at 5.958%, rounded down to 5.75%, then the review's per-account ×2. The ruled 1.41 is the trial book's 1.4060 rounded **up**. The book paper trades is the spec book, which gives 1.3923, and that rounds down to **1.39** [V `derive.py`] |
| **effective vol target** | core 0.06 × 1.24 = **7.44%**; C4 0.06 × 1.39 = **8.34%**; combined **5.75%** |
| **plateau** (§3.4) | **Yes.** Within ±0.50% of 5.75%, gross Sharpe is 1.670–1.680 total return and 1.746–1.755 price only. The Sharpe argmax (3.25%) and the return argmax (20%, a constant-gross book) are named and not chosen [V] |
| **fit path, gross** (§5) | combined **9.0%/yr total return, 9.7% price only**, Sharpe 1.67 / 1.75, on the house cap model [V `risk.py`]. On the exact implementation, **9.4% / 10.5%** at ×1.41 (9.3% / 10.4% at ×1.39) [V `impl_core.py`, `impl_c4.py`]. At C4's own-window or committed-holdout edge, **8.1% / 6.4%**, Sharpe 1.50 / 1.18 [U `edges.py`] |
| **risk, 12 months, including 2008–09** (§5.3) | Zero edge, worst method, the 10 core books as min / median / max. **Combined: P(HALVE) 2.6 / 4.7 / 13.2%, P(KILL) 0.04 / 0.15 / 1.5%.** But the runner measures drawdown **per account**: **core account P(HALVE) 10.6 / 20.1 / 52.7%, P(KILL) 0.7 / 3.6 / 18.5%; C4 account P(HALVE) 20.1%, P(KILL) 2.5%.** Today's sizing beside: core 3.8 / 10.4 / 49.6% and 0.1 / 1.2 / 16.1% [V `risk.py`] |
| **cap binding** | sessions on which the account's held book sits at its cap: core **21.7%** (today 7.3%); C4 **31.8%** over its own window and **37.6%** on 2013–22 (today 6.9% / 9.8%). These are for the exact book; the cap model's figures are higher (§5.2) [V `impl_*.py`] |
| **worst drawdown** | core account 2013–22: **14.9%** model, **15.9%** exact (today 12.8%, already past the 12% HALVE line). Core account through 2008, over the 10 books: **15.6 / 24.4 / 39.4%**. C4 account **11.2%**. Combined through 2008: **7.3 / 8.7 / 17.1%** [V] |
| **costs** (§8) | gross decides on paper. Combined net at the fit-path edge is **+7.0 / +3.0 / −3.0 %/yr** at 5 / 15 / 30bp, so the sign flips between 15 and 30bp, at a breakeven of 22.5bp. At C4's committed-holdout edge the breakeven is **15.8bp**: net is about zero at 15bp. The C4 account alone breaks even at 8–17bp. Real money is gated separately (§8) |
| **evidence** (§6) | **Forward paper only.** The core's 2023+ is not clean, and neither is C4's holdout. The trial tests whether risk scaled as modelled. It cannot test whether the raise earns more, nor the 2008 tail |
| **live stops** (§6.2) | the spec's HALVE / KILL lines (report-only); the core's 60-session kill rule; C4's H11 rule rebuilt on the raised book; and three stops specific to the raise. **R1:** drawdown past D_R (core = the 12% HALVE line; C4 ≈ 10.6%). **R2:** 120-session return below its 5th percentile. **R3:** 60-session vol above its 95th percentile. Each is re-measured on the read date by `stops.py` |
| **revert** (§9) | delete `sizing_multiplier` from that account's spec; the old spec is one `git show spec-cef_discount.v7.20260928:...` away |
| **trials** (§9) | **CEF 52 → 53 on approval, bar √(2 ln 53) = 2.818.** The raise makes no Sharpe claim, so the bar judges nothing here. Counting it raises every later CEF trial's bar |
| **open questions** (§10) | seven, each with a recommended answer |

---

## 1. What changes

### 1.1 The key, the files, the values

**New optional frozen key `sizing_multiplier`.**
- UNITS: a multiple of the unit book, not a percent, and not a vol.
- Absent (or null): today's book.

| spec | file | today | after | spec id |
|---|---|---|---|---|
| core | `ops/specs/cef_discount.frozen.json` | key absent | **`sizing_multiplier: 1.24`** | `cef_discount.v7.20260928` → `cef_discount.v8.<date>`; tag `spec-cef_discount.v7.20260928` pushed BEFORE the change (`/spec-change` step 5) |
| C4 | `ops/specs/c4_families.frozen.json` (branch `c4-integrate`; dark, not on `main`) | key absent | **`sizing_multiplier: 1.39`** (or 1.41, open question 1) | `c4_families.v1.20261029` → v2, at C4's arming. C4's cap is re-derived then anyway: its ruling (3) of 2026-10-29 |

**`vol_target_annual` stays 0.06 in both specs.** The economic change is the effective ex-ante vol
target of each account, 0.06 × m: 7.44% for the core and 8.34% for C4.

**What the sleeve does with it** (`src/deploy/sleeves/cef_discount.py::target_positions`; C4 reuses
this sleeve):
1. The unit book is built exactly as today: z-score, vol scalar `clip(0.06 / rv, 0.2, 2.5)`,
   `gross_leverage`, the `min_abs_weight` drop-and-re-neutralise, and the group cap if set. **C4's
   fidelity probe reads `w` here**, at the `min_abs_weight` read, so it sees the same object.
2. The band compares the unit target with **held / m**: `held_w = q × px / (sleeve_nav × m)`.
3. `_cap_gross` acts at **`max_gross_stress / m`** in unit weights. That is `max_gross_stress` ×
   the account's NAV, the same object gate 8 and `fit_to_buying_power` enforce.
4. Every weight target is emitted as **m × the unit weight**. A band HOLD stays in shares, unchanged.
   The dust filter at output reads the unit weight.

When the key is absent, none of those lines runs. That is the house pattern for `band_width`,
`group_cap` and `max_gross_stress`.

**The code change also carries:**
- **The registry.** `_validate_cef_discount` refuses a non-finite or non-positive m, and an m whose
  0.06 × m falls outside the existing 0.5–40% band.
- **The combiner.** `combine.load_sleeves` refuses an enabled `risk_budget` sleeve whose spec carries
  the key, naming it. The combiner has its own sizing (b × σ_book / σ_sleeve), and two sizing
  authorities in one book would compound.
- **orient.** SPEC prints the key and the effective target.
- **C4's benchmark.** `c4_paper_benchmark.h11_reference` builds the raised book (§6.2), reading m
  from the spec.

**Tests,** written and shown to fail on the old code before they are kept (CLAUDE.md):
1. Key absent: byte-identical, against the release commit's hashes, on the real panel and on the
   synthetic one. The comparison covers exit, plan.json, plan_sha, orders, targets and the run record,
   as `test_missing_nav_hold.py` pins bd87144.
2. Key present at 1.0: byte-identical. The arithmetic x / 1.0 and x × 1.0 is exact in IEEE 754, so
   this is provable, not approximate.
3. m = 1.24 on a held book whose positions are m × target: every name is a band HOLD. The old code
   would trade the book down to 1/m.
4. The emitted gross is ≤ `max_gross_stress` × NAV.
5. C4's `fidelity` passes with the key present.
6. The combiner refusal.

### 1.2 Why this implementation, and not the others (item 1)

| route | what it would take | why not / why |
|---|---|---|
| A: raise `vol_target_annual` (0.06 → 0.0744 / 0.0834) | one value per spec | **For C4 it breaks the fidelity gate.** Both `_vol_target_annual_note` and `_gross_leverage_note` on `c4-integrate` say "moving this value breaks that check (its negative control)". **For the core it trades a different book from the derived one.** The band becomes 4.8% of a book 1.24× larger (3.9% relative), and the vol-scalar clip moves. Measured on the fit, it trades 19.2 turns a year against B's 17.1, and its net Sharpe at 30bp is 0.170 against 0.233 [V `impl_core.py`]. `spec.VOL_TARGET` is also read by research code beyond the core book (the ex-date sleeve's k, PCEF's k rule, `real_money_costs`, `portfolio_baseline`), and all of that would move silently |
| raise `gross_leverage` (1.0 → m) | one value per spec | It acts before the band, so the core gets A's band narrowing. It is also C4's other named negative control |
| the combiner (`risk_budget`) | a book spec per account with σ_book = 0.06 × m, and b = 1 | b is bounded to (0, 1], and σ_book is the book spec's own value, so a one-sleeve account cannot express m > 1 without a second spec. **The combiner also refuses `data.missing_nav` with budgets** (`quantt/session/run.py` l.1207: "single-sleeve book"). The hold was switched on 2026-10-29 (cee16ad) after PDO cost the book a day, so this route would remove it |
| **B: `sizing_multiplier` (chosen)** | one new key, a few lines in the sleeve, tests | **It is exactly the model the multipliers were derived under:** m × the sleeve's decided book, one uniform cap per account. C4's compared object is untouched. The core keeps its single-sleeve path, and with it the missing-NAV hold and the stale-NAV report. The key absent is a provable no-op |

**How the combiner and the missing-NAV hold interact with B.**
- Both accounts run the single-sleeve path. `c4_families_book.json` on `c4-integrate` has one sleeve
  and no `risk_budget`, so `load_sleeves` returns None in both books.
- A name the missing-NAV hold (or the stale-NAV gate) holds keeps its current shares, out of the
  cross-section. Shares are account units, so m does not touch it.
- As today, the sleeve's own cap does not count held names. Gate 8 and `fit_to_buying_power` count
  the whole account.
- If either book ever moves to the combiner, the combiner refusal above forces the multiplier to be
  re-expressed as budgets first.

**What B does not reproduce exactly, measured** (fit, W1 2013-06-25 → 2022-12-30; C4 also over its own
window from 2005-02-22) [V `impl_core.py`, `impl_c4.py`]. The house cap model ignores the cap's
feedback into the next day's band. B does not ignore it:

| account | basis | model (what derive/risk assume) | B, exact | corr(B, model) daily |
|---|---|---|---|---|
| core ×1.24 | total return | 7.41%/yr, SR 0.950, maxDD 14.90%, turn 16.6 | **6.94%/yr, SR 0.889, maxDD 15.85%, turn 17.1** | 0.991 |
| core ×1.24 | price only | 7.74%, SR 0.964 | **7.81%, SR 0.971** | 0.991 |
| C4 ×1.41, own window | total return | 9.22%, SR 1.199, maxDD 10.81% | **10.13%, SR 1.299, maxDD 11.39%** | 0.977 |
| C4 ×1.41, own window | price only | 10.72%, SR 1.342 | **11.69%, SR 1.441** | 0.978 |
| C4 ×1.39, own window | total return | 9.14%, SR 1.198 | **10.01%, SR 1.296** | 0.978 |

**What the table means:**
- On paper's own score, price only, B matches the model for the core (+0.07%/yr). On total return it
  is 0.47%/yr below.
- C4 does better under B than under the model. Its unit book is capped at 1.90 / m ≈ 1.35, and C4's
  own cap plateau already showed Sharpe rising as the cap tightens: 1.247 at 1.60 against 1.200 at
  1.90 [doc: C4 spec `_max_gross_stress_note`].
- **So paper trades a C4 book whose effective unit cap, 1.35, lies outside the 1.60–2.00 range that
  plateau tested.** This is stated, not hidden (§7).
- None of this chose B. B was declared first, on mechanism.

---

## 2. Why, mechanically

On Reg T the scarce resource is gross, not vol [doc: `PORTFOLIO_FRAMEWORK_2026-10-15.md` §0 item 1].
At 6% the core account holds a mean unit gross of 1.21 against a cap of 1.80, and C4 holds 1.45 against
1.90 [V `derive.py` §4]. Raising the risk to the declared σ_margin uses margin the accounts already
have. Without a new signal, that is the only way to lift the percentage return on the capital the team
lead has ruled is the denominator.

- **No signal changes.** The multiplier cannot create edge. Under the house rescaling convention it
  leaves Sharpe unchanged until the cap binds, and from there it lowers Sharpe slightly as the book
  turns constant-gross (§3.4).
- **The return scales with m only while the cap is slack.** That is why the target stops at
  σ_margin, and why the cap-binding share is a headline here.
- **The graveyard** (`docs/RESEARCH_STATE.md`, CEF construction KILLED) has two sizing entries,
  "sizing up on |z|" and "sizing up on dislocation". Both are conditional sizing. A constant
  multiplier is not either of them. The sleeve's own `_cap_gross` docstring says levering up "is a
  sizing decision with its own evidence and its own trial", which is why this is a trial and not a
  configuration change.
- **What it is not.** It does not admit the ex-date short or PCEF (both OFF, as ruled). It changes no
  cap, band or signal parameter.

---

## 3. How the multipliers were derived (item 2)

### 3.1 The rule: W6's form, as the desk has written it

- **The archived W6 work order** (Part B, `pre-clean-slate:_archive/docs/prompts/W6_risk_governance.md`,
  as quoted in [doc: `PORTFOLIO_FRAMEWORK_2026-10-15.md` §2.6]) derived the target as "the largest
  whose bootstrap kill-probability is below 10% and whose margin cushion stays above 0.25 at a 3σ
  one-day move", capped at 20%.
- **The framework kept the kill-probability form.** It replaced the cushion with the adopted margin
  rule (`max_gross_stress`, CEF trial 50) and left p\* to the team lead:
  **σ\* = min(σ_cap, σ_kill, σ_margin, σ_capacity, ½·IR_net)**, on the combined book.
- **The 2026-10-28 allocation declared the rule before any combined-book number**
  (`SCRATCH/alloc/declared_threshold.json`, 2026-10-28T21:40:27Z):
  - p\* = 5%;
  - zero edge, the worst of SB21 / SB63 / GAUSS;
  - σ_margin = 1.80 × 6% / (the mean netted gross at 6%);
  - weights at equal standalone vol;
  - rounded down to the 0.25% grid.

  σ_capacity is UNMEASURED: P_max is the team lead's number.

**The terms on the two-sleeve book** (one account, one cap 1.80; W1 = 2013-06-25 → 2022-12-30):

| term | value | source |
|---|---:|---|
| σ_cap (mandate) | 20% | team lead 2026-09-08, 2026-10-09 |
| σ_kill at p\* 5%, zero edge | > 20% (zero-edge P(KILL) is 0.10% at 5.75% and 0.66% at 20%) | [doc `SCRATCH/alloc/tables/t8, t9`] |
| **σ_margin** | **5.958%** = 1.80 × 0.06 / 1.8126 | **[V `derive.py` §1, reproduces t9 to 1e-12]** |
| ½·SR_net@15bp | 31.5% | [doc t9] |
| **σ\*** | **5.75%** (σ_margin binds) | [V] |

p\* does not matter here. σ_kill is above 20% at 5% and at W6's 10% alike, so the margin term binds
either way.

### 3.2 From σ\* to the per-account multipliers

The combined multipliers are m_k = σ\* × b_k / (sd_k × sd_c), with b = ½, ½.
- The weights: every robust estimator gave about ½ / ½ for two sleeves, and the James–Stein τ² was 0
  [doc `SCRATCH/alloc/NOTE.md` §4, §5].
- At 5.75% the combined multipliers are **core 0.6219, C4 0.7030**. They reproduce t8 exactly
  [V `derive.py` §1].
- **The review's correction: multipliers are per account.** Each account is half the $200k, so its
  multiplier is ×2.

| C4 series | core | C4 | written (2 dp, **rounded down**: a risk multiplier is never rounded up) |
|---|---:|---:|---|
| trial book (cap 1.80), the derivation's input | 1.2437 | 1.4060 | 1.24 / **1.40** |
| **spec book (cap 1.90), the book paper trades and H11 reads** (team lead 2026-10-29) | 1.2439 | **1.3923** | **1.24 / 1.39** |
| spec book, price only (sensitivity) | 1.2064 | 1.3430 | — |

All [V `derive.py` §2, §3].

**The ruled 1.41 is the trial book's 1.406 rounded up.** On the book that trades, the same rule gives
1.39. The difference is 0.04%/yr of gross [V `risk.py`: 9.04% against 9.00%]. This draft carries 1.39
and asks (open question 1).

### 3.3 A second declared rule disagrees, and its price

The 2026-10-29 four-sleeve note added per-account terms (`SCRATCH/alloc4/declared_threshold.json`):
- (c): each account's P(KILL) ≤ 5%;
- (d): each account's mean uncapped gross ≤ its own cap.

The 2026-10-28 rule had neither, because it had one account and one cap.

**At 5.75% the C4 account fails term (d).** Its mean uncapped gross is 1.447 × 1.41 = **2.04** (2.01
at 1.39), against its 1.90 cap. The core is at 1.50 against 1.80, so it passes [V `derive.py` §4].

**Under the 2026-10-29 rule the same two-account book stops at 5.25%**, with multipliers **core 1.13,
C4 1.27**. That reproduces the four-sleeve note's row 1.1357 / 1.2712 [V; doc `SCRATCH/alloc4/tables/m_books.csv`].
- Its price is **−0.54%/yr** of gross: 8.50% against 9.04% total return [V `risk.py`].
- What it buys:
  - core-account zero-edge P(KILL) through 2008 falls from 3.6% to 2.4% (median book);
  - C4's falls from 2.5% to 1.6%;
  - C4's cap binds on 47% of sessions on the model instead of 68%.

The ruling is 5.75%. The conflict between the two declared rules is open question 2.

### 3.4 The plateau check, from the reviewer's model

The two-account model (each account its own cap; spec series) at combined targets 2.00–20.00%
[V `derive.py` §5, `plateau_grid_2026-10-30.csv`], with the reviewer's one-account grid beside it
[doc t8]:

| combined target | core / C4 multiplier | gross TR %/yr | SR TR | SR PR | core cap binds | C4 cap binds | reviewer's one-account: %/yr, SR |
|---:|---|---:|---:|---:|---:|---:|---|
| 4.50% | 0.97 / 1.09 | 7.61 | 1.701 | 1.775 | 0% | 21% | 7.73, 1.719 |
| 5.00% | 1.08 / 1.21 | 8.25 | 1.687 | 1.762 | 19% | 38% | 8.46, 1.711 |
| 5.25% | 1.14 / 1.27 | 8.52 | 1.680 | 1.755 | 21% | 48% | 8.75, 1.705 |
| 5.50% | 1.19 / 1.33 | 8.77 | 1.673 | 1.750 | 22% | 58% | 9.02, 1.703 |
| **5.75%** | **1.24 / 1.39** | **9.01** | **1.670** | **1.746** | **32%** | **66%** | **9.25, 1.701** |
| 6.00% | 1.30 / 1.45 | 9.24 | 1.673 | 1.749 | 38% | 71% | 9.43, 1.698 |
| 6.25% | 1.35 / 1.51 | 9.42 | 1.673 | 1.749 | 42% | 76% | 9.60, 1.696 |
| 7.00% | 1.51 / 1.69 | 9.80 | 1.662 | 1.734 | 58% | 85% | 9.94, 1.680 |

The cap-binding columns use the model's definition: the decided uncapped gross is above the cap.

- **Plateau: yes.** Every point within ±0.50% has a Sharpe within 0.05 of the derived point's. The
  range is 1.670–1.680 on total return and 1.746–1.755 price only.
- **The return keeps rising past 5.75%, but more slowly** as the caps bind: +0.23%/yr per 0.25% just
  above, against +0.34 to +0.38 around 4.5%.
- **Not chosen: the Sharpe argmax**, 3.25% (SR 1.706, 5.54%/yr). It gives up 3.5%/yr for 0.04 of
  Sharpe.
- **Not chosen: the return argmax**, 20% (10.73%/yr, SR 1.554). The caps bind on 99–100% of sessions
  there, so it is a constant-gross book that has given up the protection vol targeting provides
  [doc: `docs/BRIEF.md`, via `SCRATCH/alloc/NOTE.md` §0: −27% → −12% full-sample drawdown].
- The derived value is where the rule stops: the margin term. It is not a point picked off this table.

---

## 4. Committed in advance

- **Execution:** `shift(2)` (decide t, fill t+1, earn t+2), through `band_frontier.evaluate`. No new
  backtester. `impl_core.py` and `impl_c4.py` call `build_targets`, `band_gross_capped` and
  `evaluate`, and nothing else.
- **Score:** gross P&L is the headline. On paper that means **price only**, paper's P&L of record,
  because Alpaca pays no distributions. Total return sits beside it. The cost grid 5 / 15 / 30bp is
  labelled as the real-money view. Borrow is not charged (paper charges none); it is labelled where
  it matters (§8).
- **Eras (H5):**
  - the core is flat before 2013 (CLAUDE.md landmine 8), so its eras are 2013-06..2017 and 2018–22;
  - C4's own window starts 2005-02-22;
  - "through 2008" means W2, with the core proxied.
- **Fit ends 2022-12-30**, asserted in every helper. No 2023+ return is computed.
- **Holdout:** none is clean (§6.1). Forward paper is the only evidence.
- **Turnover matching (H2): not applicable.** This is the same policy at a different size, not two
  policies. Turnover scales with m (core 13.5 → 17.1 turns/yr exact), and the cost grid prices it.
- **Negative control:** the multiplier cannot create edge. The control is therefore the unit book
  itself. The raise is judged on whether risk scaled as modelled (R3), never on whether the return
  rose.

### 4b. Stage 0

- **No new data, and no P&L on an unruled series.**
- The core's inputs are the deployed panels the book trades on, fit-cut. The unit book reproduces
  the derivation's series to 0.0 [V `impl_core.py`].
- C4's inputs are its spec book, through its own reproduction gate: the committed 1.216958 / 1.359591
  to 1e-9 [V `impl_c4.py`]. Its Stage-0 flags and the IGR bars were ruled
  [doc: `results/cef/c4/c4_seed_rulings_2026-10-29.json`, `c4_bar_rulings_2026-10-19.json`].
- So there is no rulings file and no block. **Check before approval:** that every C4 Stage-0 flag in
  `c4_stage0_flags_2026-10-14.csv` has a recorded ruling. This draft did not re-verify that table.

---

## 5. What we expect

### 5.1 Returns at the multipliers, on the fit path

Two $100k accounts, W1, the house cap model [V `risk.py`]. The exact-implementation figures are in
§1.2.

| | multipliers | gross TR %/yr | vol | SR | gross PR %/yr | SR PR | maxDD TR (W1) | turn/yr |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| core account | 1.24 | 7.41 | 7.79% | 0.950 | 7.74 | 0.964 | 14.90% | 16.6 |
| C4 account | 1.39 | 10.58 | 7.30% | 1.449 | 11.69 | 1.547 | 10.51% | 63.4 |
| C4 account | 1.41 (ruled) | 10.66 | 7.35% | 1.451 | 11.77 | 1.548 | 10.58% | 63.8 |
| **combined, 1.24 / 1.39** | | **9.00** | 5.39% | **1.670** | **9.71** | **1.746** | 7.28% | 40.0 |
| combined, 1.24 / 1.41 | | 9.04 | 5.40% | 1.672 | 9.75 | 1.748 | 7.29% | 40.2 |
| combined, today (1.00 / 1.00) | | 7.38 | 4.38% | 1.683 | 7.95 | 1.754 | 6.15% | 30.5 |
| combined, exact implementation, 1.24 / 1.41 | | 9.37 | — | — | 10.47 | — | — | — |

The exact-implementation row is the mean of the two accounts' B figures [V].

**If the edge is lower than the fit path's** [U `edges.py`: each account's gross scaled by assumed
Sharpe / fit Sharpe, at fixed vol and turnover, ruled 1.24 / 1.41]:

| edge | C4 Sharpe used | combined gross TR | Sharpe | net @ 5 / 15 / 30bp | breakeven |
|---|---:|---:|---:|---|---:|
| fit path | 1.451 | 9.04% | 1.67 | +7.0 / +3.0 / −3.0 | 22.5bp |
| C4 own window (spec book) | 1.200 | 8.11% | **1.50** | +6.1 / +2.1 / −4.0 | 20.2bp |
| C4 holdout, corrected (the verdict) | 1.434 | 8.97% | 1.66 | +7.0 / +2.9 / −3.1 | 22.3bp |
| C4 holdout, as committed | 0.725 | 6.37% | **1.18** | +4.4 / +0.3 / −5.7 | **15.8bp** |
| half the fit path | ½ each | 4.52% | 0.84 | +2.5 / −1.5 / −7.6 | 11.2bp |

**"Realistic Sharpe 1.2–1.5" reproduces** as the span between C4's committed holdout and its own
window. The core's only v7 Sharpe that excludes 2023+ is the fit path's in-sample 0.955. Its 2024–26
holdout was opened on another configuration (§6.1), so no out-of-sample core edge is used.

### 5.2 The cap

Two definitions of how often the cap binds:
- **held at cap:** sessions on which the held book sits at the cap, from the exact build;
- **decided above cap:** sessions on which the model's decided uncapped gross is above the cap.

| account | multiplier | held at cap: exact B, W1 | decided above cap: model, W1 | mean uncapped gross (model) | today, held at cap |
|---|---|---:|---:|---:|---:|
| core | 1.24 | **21.7%** | 32.2% | 1.50 against 1.80 | 7.3% |
| C4 | 1.39 | **35.8%** (own window 30.4%) | 65.6% (own window 52.9%) | 2.01 against 1.90 | 9.8% (6.9%) |
| C4 | 1.41 | **37.6%** (own window 31.8%) | 67.5% (own window 54.4%) | 2.04 against 1.90 | — |

[V `impl_core.py`, `impl_c4.py`, `risk.py`]

### 5.3 Risk in 12 months, through 2008–09 (item 4)

**How these were computed:**
- P(max drawdown ≥ `risk.halve_drawdown` 0.12) and P(≥ `risk.kill_drawdown` 0.18) within 252
  sessions, compounded from a high-water mark.
- 10,000 paths each of SB21, SB63 and GAUSS. The **worst method** and the **worse of total return
  and price only** are shown.
- **HALVE does not act.** Report mode is today's state.
- **W1** = 2013-06-25 → 2022-12-30. **W2** = 2005-02-22 → 2022-12-30. On W2 the core before 2013-06-25
  is the house fixed-book group proxy at each of the 10 year-end core books 2013–22, shown as
  min / median / max.
- A fixed book is not vol-targeted through 2008, so **the core's W2 figures are an upper bound** [U].
  The core's real 2008 behaviour is unmeasured: the 13-name book was flat then.
- The C4 account does not depend on the core book.

All figures [V `risk.py`, `risk_output_2026-10-30.txt`]:

| statistic | edge | today (1.00 / 1.00) | **ruled (1.24 / 1.41)** | 1.24 / 1.39 | 2026-10-29 rule (1.13 / 1.27) |
|---|---|---|---|---|---|
| **combined** P(HALVE), W2 | zero | 0.4 / 1.3 / 8.7% | **2.6 / 4.7 / 13.2%** | 2.5 / 4.7 / 13.1% | 1.6 / 3.4 / 11.7% |
| **combined** P(KILL), W2 | zero | 0.00 / 0.00 / 0.48% | **0.04 / 0.15 / 1.49%** | 0.04 / 0.15 / 1.47% | 0.00 / 0.08 / 0.92% |
| combined P(HALVE) / P(KILL), W1 | zero | 1.0% / 0.01% | 3.9% / 0.09% | 3.9% / 0.09% | 2.7% / 0.05% |
| **core account** P(HALVE), W2 | zero | 3.8 / 10.4 / 49.6% | **10.6 / 20.1 / 52.7%** | same | 7.2 / 15.2 / 51.4% |
| **core account** P(KILL), W2 | zero | 0.09 / 1.2 / 16.1% | **0.67 / 3.6 / 18.5%** | same | 0.35 / 2.4 / 17.4% |
| core account P(HALVE) / P(KILL), W1 | zero | 10.6% / 0.68% | **20.3% / 2.5%** | same | 15.9% / 1.5% |
| core account P(HALVE) / P(KILL), W1 | fit | 1.8% / 0.04% | 5.0% / 0.31% | same | 3.2% / 0.16% |
| core account P(KILL), W2 | fit | 0.01 / 0.48 / 10.7% | 0.14 / 2.9 / 11.4% | same | 0.06 / 1.6 / 11.1% |
| **C4 account** P(HALVE) / P(KILL), W2 | zero | 7.1% / 0.35% | **20.1% / 2.5%** | 19.7% / 2.4% | 16.3% / 1.6% |
| C4 account P(HALVE) / P(KILL), W2 | fit | 0.5% / 0.00% | 2.6% / 0.13% | 2.4% / 0.12% | 1.7% / 0.05% |

**Read it this way:**
1. **The combined book's odds are small, and they are not what the runner measures.**
   `quantt/session/drawdown.py` measures drawdown **per account**, against the spec's lines. Per
   account, the raise roughly doubles the zero-edge chance of reaching HALVE in a year: core 10.6 →
   20.3% on W1; C4 7.1 → 20.1% through 2008. It roughly triples the chance of reaching KILL: core
   0.7 → 2.5% on W1 and 1.2 → 3.6% on the median book through 2008; C4 0.35 → 2.5%.
2. **The brief's "P(HALVE) 4–6%" is the combined book's median through 2008, at zero edge (4.7%).**
   The core account's fit-edge P(HALVE) on W1 is also 5.0%. Neither is the per-account zero-edge
   number.
3. **The GAUSS method is the worst throughout.** The block bootstraps give about half its HALVE
   odds. The core account on W1 at zero edge is SB21 8.6–10.3%, SB63 9.3–11.3% and GAUSS 18.6–20.3%,
   across total return and price only.
4. **The dangerous core books are the 1.70–1.80 gross ones** (2017-12-29, 2019-12-31). Held fixed
   through 2008, they put the core account past KILL at any multiplier, because the cap binds and
   holds them at 1.80×. The worst book's P(KILL) moves only from 16.1% to 18.5%.

**Worst drawdown** (worse of total return and price only) [V]:

| account | today | ruled | range across the 10 core books held through 2008 |
|---|---|---|---|
| core, W1 (its own book) | 12.78% TR / 13.64% PR | **14.90% / 15.59%** (exact B 15.85% / 16.00%) | — |
| core, W2 | — | — | today 13.6 / 20.1 / 36.0%; **ruled 15.6 / 24.4 / 39.4%** |
| core, the GFC window 2008-09 → 2009-03 | — | — | ruled 8.1 / 18.4 / 31.4% |
| C4, W2 (its own fit) | 9.3% | **11.2%** (trough 2011-05-25); exact B 11.4% TR / 11.9% PR | — |
| combined, W2 | — | — | today 6.1 / 7.2 / 14.0%; **ruled 7.3 / 8.7 / 17.1%** |

**Even today's core book crossed the 12% HALVE line on its own fit path** (2017-06 → 2018-06,
[doc `PORTFOLIO_FRAMEWORK` §0 item 4]). At ×1.24 it crosses it by 3–4 points.

---

## 6. What the trial can show, and what would stop it (item 3)

### 6.1 What is tested, and what evidence is clean

**H-VT, the claim tested.** At ×1.24 (core) and ×1.39 (C4), each account carries the modelled risk:
realised vol near m × the unit book's, the cap binding near the exact build's share, and drawdowns
inside the fit-edge envelope. Return scales with m to first order. **The raise claims no edge.** The
edge is the existing kill rules' business.

**No historical data can test it out of sample:**
- **The core's 2023+ is not clean.**
  - The 2024-01-01 → 2026-07-30 holdout was opened on 2026-07-31 (FAIL on net, for z 63)
    [doc: `pre-clean-slate:results/cef/HOLDOUT_OPENED.json`].
  - The v7 pre-registration then computed the deployed book over 2013-06-14 → 2026-09-21
    [doc: `PREREG_ALPACA_V7_2026-09-28.md` §5].
  - The documents still call the 2023-01-01 time holdout "sealed" (`docs/RESEARCH_STATE.md`,
    `PORTFOLIO_FRAMEWORK` §9). For this book that is no longer true. This is a discrepancy for the
    team lead, not a ruling.
- **C4's holdout** (2023-01-03 → 2026-09-30) was opened once, on 2026-10-18 [doc `docs/RESEARCH_STATE.md`].
- **The core's 2005–13 is a proxy**, not the book.

**So the only clean evidence is forward paper**, from each account's first raised session.

**What forward paper can show:**
- **realised vol against the model (R3).** On 60 sessions the relative standard error of a vol is
  about 1/√120 ≈ 9% if returns were iid. With these tails it is larger, which is why R3's threshold is
  the bootstrap's 95th percentile;
- **the cap-binding share and the gross held,** directly, in plan.json;
- **the drawdown governance working at the larger size** (R1);
- **an H11-style return check (R2),** which has little power. At Sharpe 1.2–1.5, 120 sessions give an
  expected t of 0.8–1.0.

**What it cannot show:**
- that the raise earns more;
- the 2008 tail;
- auction capacity at 1.24× the size, because paper runs no closing auction (CLAUDE.md landmine 1);
- real-money cost.

### 6.2 The live stops (H11-style)

Each is read per account, on Alpaca's end-of-day portfolio history: the P&L of record (team lead
2026-10-19).

| stop | rule | horizon | threshold today [V], re-measured on the read date by `stops.py` (H14) | action |
|---|---|---|---|---|
| spec HALVE / KILL | drawdown from the high-water mark ≥ `risk.halve_drawdown` / `risk.kill_drawdown` | any session | 12% / 18%, read from the spec. C4's spec carries no levels: step 5 decides them | **report only** (`risk.drawdown: report`); no acting mode exists |
| core kill rule (unchanged) | (a) live net Sharpe < 0; (b) slippage > 2× modelled for 5 sessions; (c) discount spread < 12% | 60 live sessions | spec `kill_rule` | KILL the book. The Sharpe is scale-free, so the raise does not move (a) |
| C4 H11 (unchanged rule, **rebuilt book**) | reverse at 120 armed sessions below the 5th percentile of 120-session price-only returns; reverse on a drawdown past the fit worst | 120 sessions / any | measured on **m × band_gross_capped(T, band, 1.90 / m)**, the book B trades, not on the 1.90 unit book. Fit-worst drawdown at ×1.41: 11.4% TR / 11.9% PR [V `impl_c4.py`] | reverse C4 |
| **R1, raise drawdown** | drawdown since the first raised session ≥ **D_R**: the largest over SB21 / SB63 / GAUSS of the fit-edge 95th percentile of the 12-month max drawdown of the raised series, worse of TR / PR, capped at HALVE | any session | **core 12.00%** (TR 11.73%, PR 12.00%: it coincides with HALVE); **C4 10.64%** at ×1.39 (10.72% at ×1.41) | **revert that account's multiplier** |
| **R2, raise return** | cumulative gross return < the 5th percentile of 120-session price-only returns of the raised series (SB21, fit edge) | 120 armed sessions | core **−3.77%**; C4 **−3.20%** | revert |
| **R3, raise vol (the falsifier)** | realised daily vol, annualised, > the 95th percentile of 60-session realised vol of the raised series (SB21) | 60 armed sessions | core **13.19%**; C4 **10.68%** (10.79% at ×1.41) | revert. **H-VT: ABSENT** |

**What R1 does and does not buy:**
- A book behaving as fitted trips R1 with at most 5% probability a year, by construction. A no-edge
  book trips it about as often as it touches HALVE: about 20% for the core.
- On the fit path itself, ×1.24 would have tripped R1 once: in the 2018 drawdown (first crossing
  2018-05-04 on the exact build). Today's ×1.0 book reports HALVE in the same episode (2018-06-04,
  total return) [V `impl_core.py`].
- With R1 acting (the rest of the year held at 1/m), the zero-edge P(KILL) falls: core W1 2.5 → 1.5%;
  core W2 at the median book 3.7 → 2.9%; C4 W2 2.5 → 0.8% [V `risk.py`].
- R1 is a partial, raise-specific arming of HALVE. It cuts the account to 0.81 or 0.72 of its size,
  not to 0.5.
- **R3 is coarse.** It fires only when realised vol is about 1.4–1.7 times the fit path's (core
  13.19 / 7.79; C4 10.68 / 7.30–7.63). That is the honest power of 60 sessions with these tails.

**The pass rule.**
- At 120 armed sessions of an account, the raise is **KEPT** if R1 never fired and R2 and R3 pass,
  and no spec kill or C4 H11 rule fired.
- The verdict is recorded as **H-VT PRESENT** (risk as modelled), **ABSENT** (R3 fired), or
  **INCONCLUSIVE** (reverted on R1 or R2 alone, which a working book also does 5% of the time), beside
  its D-code (team lead 2026-10-27).
- There is no deflated-Sharpe test, because the trial claims no Sharpe.

**Who acts.** The team lead, through `/spec-change`, the same day a stop reads true. There is no
acting mode on the runner. The implementation commit adds an R1 line to the drawdown report (report
mode, with a test), so the stop is visible and not remembered.

---

## 7. Divergences from the backtest, stated up front

1. **The exact construction is not the model** (§1.2). Core: −0.47%/yr on total return, +0.07% price
   only. C4: +0.9–1.4%/yr. C4's effective unit cap is 1.35, outside its tested 1.60–2.00 plateau.
2. **The cap at the send is not uniform.** `fit_to_buying_power` scales opening orders only and sends
   reductions in full. Gate 8 judges an adding plan on the lower of sized and live equity. The
   backtest scales the held book by one f.
3. **Whole shares, `min_trade_usd`, and the dust filter on unit weights.** A 0.5% unit weight is
   0.62% of NAV at ×1.24.
4. **Paper fills at the quote, 8 to 2 minutes before the close** (`late_market`). There is no
   auction. The core's closing-cross participation rises by m on a real-money account
   [doc: `EXEC_CAPACITY_OPEN_CROSS_2026-10-13.md`: 10% of the cross at about $0.17m].
5. **Paper pays no distributions, charges no borrow and processes no corporate actions.** The
   corporate-action gate halts instead.
6. **The missing-NAV hold** keeps a name's shares for up to 2 sessions, and the stale-NAV gate runs
   in report mode. Neither is in the backtest.
7. **C4 skips shorts Alpaca will not lend**, with no substitute.
8. **The switch.** C4's first session is already raised, and trades its first book at full target
   (band skipped). The core's first raised session starts from a held ×1.0 book, and the band acts
   on held / m, so the raise phases in as names leave their bands. **Measured:** switching the held
   book to B at each year-end 2013–21 leaves its gross within 5% of B's own path on the first
   session in 6 of 9 cases, after 1–3 sessions in 2 more, and after 22 sessions at 2020-12-31
   [V `impl_core.py`, RAMP]. The ramp is short because B's own band holds a mean gross of 1.35, which
   is only 1.12× today's 1.21, not 1.24×. Realised vol rises 1.20× (6.50% → 7.81%). R3 is one-sided
   (vol too high), so a slow ramp cannot trip it.
9. **The core's 2008 behaviour is unmeasured** (W2 is a fixed-book proxy).

---

## 8. Costs (item 5)

**Gross decides.** Paper is scored on gross P&L with no borrow or execution cost (team lead D19/D20,
2026-09-15), price only. The cost grid is the real-money view, beside it [V `risk.py`; model, W1,
total return]:

| account | gross %/yr | net @ 5 / 15 / 30bp | breakeven | flips sign? |
|---|---:|---|---:|---|
| core ×1.24 | 7.41 | +6.58 / +4.91 / +2.42 | 44.5bp | no |
| C4 ×1.41 | 10.66 | +7.47 / +1.09 / −8.48 | **16.7bp** | yes, between 15 and 30 |
| **combined** | **9.04** | **+7.02 / +3.00 / −3.03** | **22.5bp** | **yes, between 15 and 30** |

**Net turns negative at about 15bp once C4's edge is below its fit path's:**
- at C4's own-window Sharpe, the C4 account breaks even at 13.8bp;
- at its committed-holdout Sharpe, the combined book breaks even at 15.8bp and the C4 account at
  8.4bp [U `edges.py`];
- C4's committed holdout was −0.304 net at 15bp [doc].

On the fit path the combined book still clears 15bp. The raise does not change cost per unit of
turnover. It scales turnover with m, so it scales the drag with it.

**Real money is gated separately, and nothing here touches it:**
- capital is deferred until Alpaca Canada (team lead 2026-10-28);
- "the real-money cost re-run is the gate for deploying any capital" (2026-10-09);
- C4 is paper only by ruling (2026-10-19), and its borrow has never been measured;
- the `late_market` exception never applies to a live account.

**Under the framework, a raise on real money also needs:**
- HALVE / KILL armed;
- the cost gate passed;
- a positive ½-Kelly at 15bp [doc `PORTFOLIO_FRAMEWORK` §2.6].

---

## 9. The revert and the trial count (item 6)

**REVERT, per account, independently.**
- **Delete `sizing_multiplier`.** The sleeve is then today's book, byte for byte: tests 1 and 2.
- Or restore the whole old spec: `git show spec-cef_discount.v7.20260928:ops/specs/cef_discount.frozen.json`.
- `vol_target_annual` was never changed, so "set it back to 0.06" has nothing to do.
- A revert is itself a spec change: a new spec id, through `/spec-change`, recorded in the stop's
  row in `docs/RESEARCH_STATE.md`.

**The trial.**
- **CEF 52 → 53**, in the commit that records the team lead's approval, not before (`/prereg`).
- One trial covers both accounts: one rule, one derived pair, one decision (open question 6). Changes
  to the live CEF book stay on CEF (team lead 2026-10-09), and C4 is itself CEF trial 52.
- **Bar at N = 53: √(2 ln 53) = 2.818** (2.811 at N = 52).
- The raise is judged by §6.2, not by the bar. Counting it raises the bar every later CEF trial must
  clear.
- Updated in `docs/RESEARCH_STATE.md` in the same commit as the approval: **yes** (2026-11-01, the
  approval commit). The draft, written 2026-10-30, did not move it.

---

## 10. Open questions for the team lead, each with a recommended answer

1. **C4's multiplier: 1.41 as ruled, or 1.39?** 1.41 is the trial book's 1.406 rounded up; 1.39 is the
   same rule on the spec book, rounded down. **Recommend 1.39.** The spec book is what paper trades
   and what H11 reads (your 2026-10-29 ruling), and a risk multiplier is not rounded up. It costs
   0.04%/yr.
2. **Which declared rule governs this book: 2026-10-28 (5.75%) or 2026-10-29 (5.25%)?** At 5.75% the
   C4 account's mean uncapped gross is 2.01–2.04 against its 1.90 cap, so the later rule's term (d)
   fails. **Recommend 5.75% as ruled, with the override of term (d) recorded in `docs/SYSTEM.md` §5.**
   The reasons:
   - the cap is enforced in the sleeve and again at the send;
   - under the exact implementation, C4 holds at its cap on 30–38% of sessions, not the model's
     53–68%;
   - its fit Sharpe rises rather than falls;
   - each account's median P(KILL) through 2008 stays under 5% (term (c)).

   The alternative, 5.25% (×1.13 / ×1.27), costs 0.54%/yr.
3. **Does this ruling waive the framework's gate on any vol increase** (HALVE / KILL armed, the cost
   gate passed, 20 armed Alpaca sessions with fills, p\* stated; `PORTFOLIO_FRAMEWORK` §2.6)?
   **Recommend: yes, for paper only, recorded,** with R1 as the raise's own partial arming. Never for
   real money. p\* = 5% was stated by the 2026-10-28 declaration. The count of armed sessions with
   fills is UNMEASURED here (`python3 -m ops.orient` PROD).
4. **Approve R1–R3 as written, with the team lead acting the same day?** For the core, R1 coincides
   with HALVE, so a HALVE report means "revert the raise". **Recommend yes,** and an R1 line in the
   drawdown report (report mode, tested) in the implementation commit.
5. **When does each account start?** **Recommend:**
   - the core on its first session after the release that carries v8;
   - C4 at its own arming (plan §2 step 6), already at its multiplier, with its H11 reference and
     drawdown stop rebuilt on the raised book (§6.2);
   - the 60- and 120-session clocks run per account.

   Until C4 trades, the core runs at ×1.24 alone. Its account risk is the table's core row; the
   combined rows do not apply yet.
6. **One trial or two?** **Recommend one (CEF 53), judged at N = 53.** The two multipliers are one
   rule's output.
7. **The documents that still call the core's 2023+ "sealed".** **Recommend a dated correction
   note** in `docs/RESEARCH_STATE.md` and `PORTFOLIO_FRAMEWORK` §9, saying that 2024–26 was opened on
   2026-07-31 and that 2023+ was computed by the v7 note. Otherwise a later trial may treat it as clean.

---

## 11. Reproduce

`SCRATCH` is the session scratch folder holding the allocation series (`alloc/series.py`,
`alloc_review/r2_series.py`, `alloc4/series4.py c4`, `alloc4/proxy4.py`). Those series are
CRSP-derived for C4, so they are never copied into the repository.

```bash
cd results/cef/prereg_voltarget
python3 derive.py   --scratch SCRATCH                    # §3: the rule, x2, the spec book, term (d), the plateau (1 s)
python3 risk.py     --scratch SCRATCH                    # §5.3, §8: per-account odds W1/W2, drawdowns, costs, stops (about 5 min)
python3 edges.py                                         # §5.1: gross and net at lower edges [U]
python3 impl_core.py --scratch SCRATCH --m 1.24          # §1.2: the core's exact B and A builds (fit-cut panels it makes itself)
python3 -I impl_c4.py --scratch SCRATCH --c4-tree WORKTREES/c4-step2-spec --m 1.41 --m 1.39   # §1.2: C4's exact B (about 4 min)
python3 stops.py    --scratch SCRATCH --m-core 1.24 --m-c4 1.39   # §6.2: R1-R3 re-measured (the read-date tool)
```

**Outputs:**
- `declared_2026-10-30.json`, written first;
- `derive_*`, `plateau_grid_*`, `risk_*`, `edges_*`, `impl_core_*` and `impl_c4_*`, each `.json` plus
  `_output_*.txt`.

**Panels' last dates.** All were read only to 2022-12-30. The core's fit cut has `cef_prices` and
`cef_nav` to 2022-12-30 and `cef_distributions` to 2022-12-28. C4's families cut has prices and NAV to
2022-12-30 and actions to 2022-12-29 [V].

**Code:** this tree at origin/main 35b429f, and C4 at `c4-step2-spec` 6f62527 (asserted clean).
