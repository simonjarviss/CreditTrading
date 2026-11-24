# The portfolio framework: one account, the discount book plus any number of event sleeves — 2026-10-15

**The question** (team lead, 2026-10-15): *"after we can find all sub event driven /
special situation trading strategies systematically we would need a portfolio level
overview to optimize our trading"*. This note designs that portfolio layer for the
one Alpaca account the sleeves share (`docs/SYSTEM.md` §5, 2026-10-09: "inside the CEF
account, one combined book").

**Status.** Design note plus a zero-trial measurement of the live book's own risk.
**It spends no trial** (CEF stays 52, EVENTS 0, XASSET 4, GAMMA 0), changes no spec,
touches nothing on the live path and sends nothing to a broker. Every rule below
says what to measure at run time and what follows under either outcome (H14).

**Reproduce every measured figure (§6):**

```bash
python3 scripts/data/stage_crsp_w4.py        # CRSP ETF returns to 2022-12-31 (R2, read-only; QUANTT_ENV_FILE)
python3 scripts/data/fetch_ff_factors.py     # Ken French FF5 + UMD (primary source)
python3 scripts/cef/portfolio_baseline.py    # -> results/cef/portfolio_baseline/portfolio_baseline_output.txt
python3 -m pytest scripts/cef/tests/test_portfolio_baseline.py
```

The run takes about two minutes, most of it the bootstrap. Its output holds ratios
and statistics only, no account figure.

**Panels**, as read for the run (2026-10-15): `cef_prices` to 2026-10-15 and `cef_nav`
to 2026-10-14. The shared panels were refreshed at 16:24 local time, after orient read
2026-09-28 / 2026-09-25 at the start of the session and before every run here. The rest:

- `cef_distributions` to 2026-09-10;
- `cef_borrow_history` 2021-09-13 → 2026-09-09;
- French daily factors, CRSP vintage 202608, to 2026-08-31;
- the W4 CRSP cache to 2022-12-30.

**Only rows to 2022-12-30 enter any return, position or covariance.** The one later
input is the P3 borrow fee level, read as a cost input exactly as
`results/cef/REAL_MONEY_COSTS_2026-10-12.md` did. The headline reproduces that note
and W4 §6d to the printed digit, so the refresh did not move the fit window.

**Labels.** `[V]` verified this session, by the command named. `[S]` sourced, not
re-read. `[U]` uncertain. `[doc: path]` copied from a repo note and not re-run here.
The design reads the archived W6 work order
(`pre-clean-slate:_archive/docs/prompts/W6_risk_governance.md`) as the brief that "the
vol target is derived under W6" points to. It is provenance, not authority, and its
figures are 17-name and pre-v7.

---

## 0. The answer

**Recommendation in one line:** keep the vol target at the spec's 6% and arm
HALVE/KILL now. Build the multi-sleeve combiner before admitting any second sleeve,
and size sleeves by a constrained Σ⁻¹·IR whose binding constraint, on Reg T, is
gross and not vol.

1. **Under Reg T the scarce resource is gross, not volatility.** On 2013-06 → 2022 the
   deployed book earned **5.15%/yr per unit of gross held** (gross of costs; 3.47% net
   of 15bp) [V]. Held at the frozen 1.80× stress cap every session, that is **9.27%/yr
   gross, 6.25% net of 15bp**. The book's vol at the cap is about **10.2%**. So:
   - no vol target gets the CEF book alone to the ≥10%/yr target on Reg T;
   - the 20% cap is unreachable on Reg T (a 20% book would need 3.5× gross);
   - the route to 10% is sleeves that earn more per unit of gross than this book,
     netting across sleeves, or Portfolio Margin (plan 4.2).

   The allocator therefore prices gross explicitly (§2.5). Its shadow price turns
   "rank by return per unit of risk" into "rank by return per unit of margin" when
   margin binds.
2. **Allocation: admit, then size** (§2):
   - admit only sleeves that passed their trial, holdout, cost gate and review;
   - size them by Σ⁻¹·IR* on vol-normalised sleeves, with three protections:
     - Σ is a Ledoit–Wolf constant-correlation shrink of 21-session P&L
       correlations, floored at the stress-block correlation;
     - IR* is the **holdout** net Sharpe, shrunk empirical-Bayes toward the
       cross-sleeve mean;
     - **no IR information is used until four sleeves are admitted**: until then
       the weights come from correlations alone.
   - Event sleeves are capped per event and per cluster by formulas derived from the
     sleeve's budget and the spec's own drawdown lines.
3. **The vol target (W6), derived, not picked** (§2.6): σ* = min(20% cap, σ_kill,
   σ_margin, σ_capacity, half-Kelly). For the CEF book alone today:
   - σ_margin ≈ **10.2%**;
   - σ_kill, the vol at which the chance of touching the 18% KILL line within twelve
     months is at most p*, under **zero edge**: **9.0–10.7% at p* = 5%** and
     **10.4–12.2% at p* = 10%**, the range spanning three bootstrap methods;
   - in the 2021–22 borrow regime (P1), even **6% gives a 24–30% chance of touching
     the 12% HALVE line within a year**.

   So the derived ceiling for the CEF book alone is about **9–10%**, and margin-bound.
   **Hold 6% until the W6 gates pass** (§2.6). On today's evidence the gates are
   HALVE/KILL unarmed, the real-money cost gate failed, and a short Alpaca record.
4. **Risk governance is absent on the Alpaca path, not merely disabled** [V: grep,
   2026-10-15]:
   - no code reads `risk.kill_drawdown`, `risk.halve_drawdown` or the book json's
     `book_drawdown_suspend_pct`;
   - the runner never calls any sleeve's `risk_check`.

   The deployed book's own worst fit-window drawdown, **12.78%** (2017-06-05 →
   2018-06-12, recovered 2019-04-02, at 6.5% realised vol), would have crossed the
   spec's 12% HALVE line. Arm it first (§3.4, §7 phase B).
5. **The book is not cleanly over its own alpha-only bar** (§6.4):
   - on a Dimson credit/rates/muni/loans/equity model its alpha t is **2.999** and
     its largest vol-scaled beta **0.094** (rates);
   - on W4's model the alpha t is 2.87, with muni β 0.144 (reproduced to the digit).

   None of these betas is significant (|t| ≤ 1.5), but the book sits on the D4
   boundary. Every sleeve's residual beta adds to it, so the book-level beta limit
   in §3.1 is not slack.
6. **Breadth is better on the 13 names than the 17-name figures say, and the group
   bet is still a fifth to a third of the risk** (§6.5). On 2,378 fit-window
   sessions:
   - effective breadth has a median of **3.48** (p10 2.13, p90 6.07);
   - the four-group between-group bet carries a median **20.1%** of ex-ante
     variance (p90 57.7%), and **30.4%** of realised P&L variance;
   - the muni-vs-taxable share is small in the fit window (median 2.4%) only
     because the ADV filter rarely admitted the munis then.

   **Today's live group share is not measured here.** Positions stay on the VM.
   W10-B put today's book at 67% between [doc: `results/cef/W10_PARTB_2026-10-12.md`].
   Measuring it daily is the dashboard's first job (§5).
7. **Tail** (§6.3, §6.8): the last fit-window book, held fixed through 2008-09 → 2009-03
   with no reaction, loses **13.8%** peak to trough at its own 0.83× gross:
   - **27.7%** at the 1.80× cap, past KILL;
   - **19.0%** if the shorts are recalled and the longs held.

   The 13-name book has never traded 2008: the ADV filter left it flat until 2013-06.
8. **Capacity**: against ADV the book is tiny, with the median day's largest trade
   **0.067%** of 63-session ADV at $100k [V]. Against the closing cross, the pool an
   MOC book actually trades in, it already binds at $100k
   [doc: `results/cef/EXEC_CAPACITY_OPEN_CROSS_2026-10-13.md` §5]. Capacity scales
   with **capital × vol target**, so raising the vol target spends capacity one for
   one.

**What I am giving up** by holding 6%: about 3%/yr of gross P&L on paper, the gap
between 6.21% and the 9.27% at the cap. The paper score is gross of borrow and of
auction impact, so that is an upper bound on what real capital would forgo.

---

## 1. Sleeve types, risk units, and estimating from sparse data

### 1.1 The two kinds

| | **C: continuous cross-sectional** | **E: discrete event** |
|---|---|---|
| examples | the live discount book; C4-like family books (`results/cef/C4_RESULT_2026-10-14.md` on branch `trial-c4`: fit PASS, holdout pending) | NAV-for-NAV merger pair (E1), conditional-tender tracker (N1), CEF IPO pair (E4), rights-offering window, term-CEF events (`results/cef/EVENT_DRIVEN_POD_2026-10-12.md` §4) |
| positions | every eligible name, every day, by a signal | 0 … K live deals, each entered on an `observed_at` and exited at a known or modelled resolution |
| risk unit | **the sleeve's daily P&L as a fraction of book NAV**, vol-targeted inside the sleeve to its budget b_s | **the event**: its loss given the adverse outcome (deal break, no trigger, pro-ration) as a fraction of book NAV, plus its daily mark while live |
| return model | Sharpe of the sleeve's net P&L at measured costs | E[r_e] = p·G − (1−p)·L − c·turn − borrow·h, per event |
| risk model | daily covariance with the other sleeves; factor betas | diffusive (mark) + **jump** (resolution); jumps cluster by sponsor, acquirer and regime |
| evidence | thousands of sessions, few independent bets (breadth §6.5) | tens of independent clusters at best (G1c and N1 counted ≥ 30 as the bar) |
| failure mode to fear | D3 (fit does not survive), D2 (costs), D4 (beta) | D7 (too few events), D4/D5 (a short put: Mitchell & Pulvino 2001 [V abstract, `docs/REFERENCES.md` §12d]), backfill and survivorship bias |

### 1.2 Continuous sleeves: what feeds sizing

- **Fit for admission, holdout for size, live for kill.**
  - The fit-window Sharpe is selection-biased: it is the survivor of N trials on
    its counter. So it only **admits**: deflated Sharpe on the counter's N, D-codes,
    the pre-registered stages.
  - The **size input** is the net Sharpe on the sleeve's opened holdout at the
    measured cost, its only out-of-sample estimate. When the holdout is shorter
    than its minimum track record length (MinTRL, Bailey & López de Prado 2012
    [V], `docs/REFERENCES.md` §7), its standard error is large and the shrinkage
    below discounts it automatically.
  - Live sessions update the size input by precision-weighting holdout and live,
    both out of sample. They decide the **kill** only at the pre-registered horizon
    (§4.1).
- **The net Sharpe, never the gross.** Paper is scored gross (D19/D20), but capital
  is allocated on net:
  - the measured cost, or the 15bp grid point until measured;
  - the measured borrow regime, with the proxy labelled.

  A sleeve whose net at the measured cost is ≤ 0 gets **zero capital budget**. On
  paper it may run at the evidence floor (§2.12).
- **The vol-per-gross figure σ₁,s** (annualised P&L vol per unit of gross held) is
  measured for every sleeve. It converts a vol budget into gross, which is what
  margin binds (§2.5). The CEF book's is **5.65%** (5.39% by the second method) on
  2013-06 → 2022 [V §6.2].

### 1.3 Event sleeves: the per-event model

For event e with position x_e (fraction of NAV), per-dollar gain g_e if it resolves
favourably, per-dollar loss ℓ_e if it breaks, and probability of a break q_e:

- **Expected P&L** per event: x_e·[(1−q_e)·g_e − q_e·ℓ_e] − x_e·(round-trip cost) −
  x_e·(borrow on the short leg × holding days).
  - Enter only if it is positive at the **posterior** q_e (§1.4).
  - Enter only if the sleeve's calibration test (Brier score against the base rate)
    passed in the fit (`EVENT_DRIVEN_POD` §6.2c).
  - A miscalibrated probability sized into a position is "sizing up on |z|" again.
- **Jump variance** of one event: q_e(1−q_e)·x_e²·(g_e + ℓ_e)².
- **Diffusive variance** while live: the deal spread's own daily vol × x_e,
  measured on the event history's marks.

### 1.4 Estimating from sparse event data (no sweeping)

| quantity | estimator | why |
|---|---|---|
| break probability q per event type | **beta-binomial**: a Beta(α, β) prior fitted by moments to the outcomes of the **family** (e.g. "NAV-convergence events": tenders, conditional tenders, NAV-for-NAV mergers, liquidations, open-endings), posterior mean (breaks + α)/(n + α + β) per type | a type with 4 events borrows strength from its family; a type with 400 is barely moved |
| gain g and loss ℓ per type | **empirical-Bayes partial pooling**, θ̂_type = w·y_type + (1 − w)·μ̂_family, w = τ²/(τ² + se²) (Morris 1983 [S], `docs/REFERENCES.md` §7) | the shrinkage weight is derived from the noise in each type's own estimate, not chosen |
| τ² with few types | a **weakly informative half-Normal prior on τ** rather than the moment estimator (Gelman 2006 [S], `docs/REFERENCES.md` §7) | the moment estimator collapses to 0 or explodes with 3–5 groups |
| standard errors | **clustered by the independent unit**: acquirer group, sponsor, announcement month. Never by event | sponsor waves (N8) make events within a family one bet |
| prior for a new family with no history | an external base rate only if it is fetched and [V] in `docs/REFERENCES.md`; otherwise the family **does not trade** | no invented prior |
| backfill | rows found by a later search are flagged `backfilled` (`EVENT_DRIVEN_POD` §3.6); every estimate is reported with and without them | a 2026 search knows events a 2015 trader may not have seen |
| survivorship | CRSP delisting returns for merged and liquidated funds | the event names are exactly the ones the live panel lacks |

**Minimum evidence (derived, not a fixed count).** To detect the pre-registered mean
per-event P&L μ against zero, at two-sided 5% and 80% power, with cluster-level
standard deviation s, a sleeve needs about **N_clusters ≥ (1.96 + 0.84)²·(s/μ)² ≈
7.85·(s/μ)²** independent clusters. The desk's "≥ 30 independent groups" (G1c, N1)
is that rule at s/μ ≈ 2. D7 (fewer than about 250 independent trades) still applies
to any claim about a *policy* rather than a mean. **A sleeve below its N does not
trade**, at any size, on paper or live. Its idea folds into C1-style hygiene
(`EVENT_DRIVEN_POD` §4.3).

---

## 2. Allocation

### 2.1 Admission (ordered; each a gate, none a weight)

1. Pre-registered trial passed every fit stage on its counter (deflated Sharpe at
   that counter's N; D1–D7 clear; the D4 test with alpha t ≥ 3.0 and every |β| ≤
   0.10 on the §3.1 factors).
2. Holdout opened once, and its sign agrees with the fit.
3. **For real capital:** the real-money cost gate on that sleeve, with measured
   borrow, distributions owed and auction cost
   (`results/cef/REAL_MONEY_COSTS_2026-10-12.md` is the shape).
4. A validation note by a reviewer who did not build it (`EVENT_DRIVEN_POD` §7.1).
5. A frozen-spec file of its own that defaults to "absent = not traded", and a
   byte-for-byte no-op proof that adding it leaves every other sleeve's targets
   unchanged (`/spec-change`).
6. A pre-registered H11 statistic and horizon (§4.1).
7. For event sleeves: N_clusters ≥ 7.85·(s/μ)² (§1.4), and the event log live with
   `observed_at` asserted (`EVENT_DRIVEN_POD` §3.6).

### 2.2 The risk unit for allocation

Every sleeve is run vol-normalised inside itself, as the discount book is today
(`vol_target_annual`). The allocator chooses each sleeve's **risk budget b_s**: its
annualised vol as a fraction of book NAV. The sleeve's own scalar then targets b_s.
An event sleeve's b_s is a **ceiling, not a target**. With few live events it runs
below budget, and the unused budget is not given to the remaining events (§2.8).

### 2.3 Expected IR: shrink it, and ignore it until it can be estimated

- IR̂_s = the size input of §1.2 (holdout net Sharpe at the measured cost), with
  se_s = √((1 + ½·IR̂²)/T_years) (Lo 2002 [V indirect], `docs/REFERENCES.md` §7).
- **Shrink toward the cross-sleeve mean**, not toward zero:
  IR*_s = IR̄ + w_s·(IR̂_s − IR̄), with w_s = τ²/(τ² + se_s²).
  - Admission already removed the sleeves with no edge, so the question is only how
    far the IRs differ from each other.
  - τ² is the method-of-moments cross-sectional variance net of the mean se²,
    floored at zero.
- **With fewer than four admitted sleeves, w_s = 0.** Every IR* equals IR̄, and the
  weights become **b ∝ R̃⁻¹·1**: maximum diversification on vol-normalised sleeves.
  - Why four: shrinkage toward an *estimated* mean dominates the per-sleeve
    estimate only from four means up (James & Stein 1961; Efron & Morris 1975 [V],
    `docs/REFERENCES.md` §7, stated there for m ≥ 3 toward a fixed point; one more
    is spent estimating the mean).
  - With two or three sleeves the IR differences are noise the optimiser would
    amplify ("error-maximization", Michaud 1989, as cited by Ledoit & Wolf 2003 [V]).
  - **This is the policy least sensitive to the input we do not know.**

### 2.4 The correlation matrix

- **Input:** the sleeves' P&L in their common fit window, as **21-session sums**.
  Daily correlations of thinly traded CEF books understate co-movement: C4's daily
  ρ with the book is +0.012 against +0.145 on 21-session sums
  [doc: `C4_RESULT_2026-10-14.md` §2, branch `trial-c4`].
- **Shrinkage:** Ledoit–Wolf toward the constant-correlation model,
  R̃ = δF + (1 − δ)S, with F's off-diagonal set to the average sample correlation
  and δ by their closed-form intensity (Ledoit & Wolf, "Honey, I shrunk the sample
  covariance matrix", working paper June 2003, published JPM 2004 [V], read
  2026-10-15; `docs/REFERENCES.md` §12u).
- **Stress floor:** each pair uses max(ρ̃, ρ_stress), where ρ_stress is measured on
  the worst-quintile HY-stress blocks, C4's own method. C4's stress ρ was +0.317
  against +0.145 overall [doc]. Diversification that disappears in a sell-off is
  not sized as if it held.
- **Event sleeves have too little P&L history for a sample correlation.** Their row
  of R̃ comes from a factor model:
  - β_E on the §3.1 factors, estimated pooled by family (§1.4);
  - plus the jump term's co-occurrence with the continuous book's worst months.
    That is assumed perfect (ρ = 1) unless the event history shows otherwise on
    ≥ N_clusters episodes. Breaks cluster in 2008 and 2020 [S: Mitchell & Pulvino
    2012, `docs/REFERENCES.md` §12].

### 2.5 The optimiser, and why gross enters it

Maximise expected return Σ_s b_s·IR*_s subject to:

- book vol √(b'R̃b) ≤ σ* (the W6 target, §2.6);
- **gross** Σ_s ν_s·b_s/σ₁,s ≤ G_stress (Reg T, §2.7). Here ν_s ≤ 1 is the sleeve's
  measured netting factor against the other sleeves;
- b_s ≥ 0, b_s ≤ capacity cap_s (§2.9), and the event caps (§2.8).

The first-order condition gives the allocation in closed form wherever the
constraints are smooth:

**b ∝ R̃⁻¹·(IR* − η·ν/σ₁)**

η is the shadow price of gross: zero while vol binds first, positive once gross binds.

- **Vol binds first (η = 0):** b ∝ R̃⁻¹·IR*, the standing rule (team lead,
  2026-09-08: "Σ⁻¹·IR, may be zero").
- **Gross binds (η > 0):** each sleeve's IR is charged η·ν_s/σ₁,s. A sleeve that
  needs a lot of gross per unit of risk is charged most: a dollar-neutral,
  low-vol-per-gross CEF book. The ranking becomes return per unit of margin,
  (IR*_s·σ₁,s − η·ν_s)/σ₁,s.
- **Today the CEF book is near both edges at once.** σ_margin ≈ 10.2% and σ_kill ≈
  9–11% (§2.6). So a second sleeve with the same return per unit gross adds
  Sharpe but almost no return. **C4 is such a sleeve.** It earns about 5.3%/yr per
  unit of gross held [doc-derived: 7.16%/yr at mean held gross 1.34,
  `C4_RESULT_2026-10-14.md` §2], against the book's 5.15%.

Solve the constrained problem as a small QP (scipy, at most a few dozen
variables) at each allocation review. Report which constraint binds and its shadow
price, so "what binds" is a measured output and not a belief.

### 2.6 The combined vol target (W6, cap 20%)

**σ* = min(σ_cap, σ_kill, σ_margin, σ_capacity, ½·IR_net)**, each measured on the
**combined** book at the review. The CEF-alone values are measured here as the
baseline (§6.2, §6.7):

| constraint | definition (measure at run time) | CEF book alone, live fit window [V §6] |
|---|---|---|
| σ_cap | the mandate ceiling (team lead, 2026-09-08) | 20% |
| **σ_kill** | the largest vol at which **P(max drawdown ≥ `risk.kill_drawdown` within 252 sessions) ≤ p\***. Measured on the book's own daily P&L rescaled. Three methods: stationary bootstrap with mean block 21 and 63, and Gaussian. **Taken under zero edge** (the series demeaned) and under the shrunk net series, and **the smaller is used**: the edge is the input we do not know | zero edge, p* = 5%: **10.7 / 10.2 / 9.0%**. p* = 10%: **12.2 / 12.0 / 10.4%**. Net 15bp + P3 borrow, p* = 10%: 15.4 / 15.5 / 12.5%. **Net 15bp + P1 borrow: 7.6 / 7.3 / 7.1% at 10%** |
| σ_margin | G_stress × σ₁,book: the vol the book carries at the stress cap | **10.2%** (1.80 × 5.65%) |
| σ_capacity | current σ × min over sleeves of (P_max / P_s at today's capital), with P_s the participation in the auction the sleeve trades. **P_max is a team-lead number, not set here** | already binding for real money at $100k in the closing cross [doc: EXEC_CAPACITY §5]; not binding on paper, which runs no auction |
| ½·IR_net | half-Kelly on the shrunk net Sharpe (full Kelly vol = Sharpe) | 0.27 at 15bp + P3 (Sharpe 0.53): **not binding**; negative under P1, which makes it the binding zero |

**What the archived W6 rule says, and how this differs.** W6 Part B derived the
target as "the largest whose bootstrap kill-probability is below 10% and whose
margin cushion stays above 0.25 at a 3σ one-day move", capped at 20%.

- This framework keeps the kill-probability form.
- It replaces the 0.25 cushion with the **adopted** margin rule, `max_gross_stress`
  (CEF trial 50: initial margin plus the worst 5-session loss per unit gross ≤ NLV).
  That rule is the spec's authority.
- **p\* is the team lead's to state** (§8). The 10% in W6 is a proposal from an
  archived prompt, not a decision.

**The HALVE line binds earlier than the KILL line.** Under zero edge, the vol at
which P(touch 12% within a year) ≤ 10% is **7.9 / 7.8 / 6.7%** [V §6.7]. A 9–10% book
should expect to halve within a year with more than 10% probability if it has no
edge. That is acceptable only if HALVE is armed: it is the mechanism that keeps a
bad year from becoming a KILL.

**The recommendation, with its derivation:**

- **Today: σ* = the spec's 6%.** σ* is gated, not computed, while any of these hold:
  - HALVE/KILL are unarmed (§3.4);
  - the real-money cost gate is failed (its P1 row makes ½·IR_net negative);
  - fewer than 20 armed Alpaca sessions with broker-confirmed fills exist (W6's gate);
  - p* is unstated.
- **After the gates, for the CEF book alone:** min(20, 9.0–10.7 at p* = 5%, 10.2) =
  **about 9–10%, margin-bound**. That earns about 9.3%/yr gross at the cap on the
  fit evidence.
- **The binding constraint is margin, then the kill line.** With sleeves admitted,
  the same formula runs on the combined book.

**What would change it:**

- Portfolio Margin (plan 4.2), which lifts G_stress;
- a borrow-aware short rule that holds net Sharpe positive in a high-fee regime
  (`REAL_MONEY_COSTS` "What would change the verdict" 2);
- a sleeve with higher return per unit gross.

**Downside if wrong.**

- If the true edge is near the fit and fees stay low, holding 6% forgoes about
  3%/yr gross on paper.
- If the edge is zero, a 9–10% book has about a 5–10% chance of touching KILL within a
  year, depending on the method, and more than 10% of touching HALVE. If fees revert
  to 2021–22 (P1), it is far worse.

### 2.7 Gross and net under Reg T, the stress cap and one account

- **One gross budget for the account.** Alpaca margins the account's net position per
  symbol, so the stress cap applies to the **netted** book, not to the sum of the
  sleeves' gross.
- **Re-derive `max_gross_stress` on the combined book at each promotion**, by the
  frozen rule G_stress = (NLV − M_other)/(m + w5)/E_book. Here w5 is the worst
  5-session total-return loss per unit gross of the **combined** sleeves' backtest.
  This is the spec note's own instruction: "re-derive by this rule at a promotion,
  never re-tune on P&L".
  - Diversification lowers w5, which lifts the cap a little.
  - An event sleeve with jump risk raises w5, which lowers it.
- **Net exposure.** The discount book is dollar-neutral by construction; event pairs
  are hedged by design.
  - The book-level limit is on **factor beta** (§3.1), not on dollar net. Dollar
    net on CEFs is not beta: the four groups carry different NAV betas.
  - A dollar-net limit is kept as a hygiene alarm only. It is measured daily and
    has no automatic action.
- **Units.** Every limit is either a multiple of NLV or a fraction of NLV, named so.
  The book json's `book_drawdown_suspend_pct` is a **whole-number percent**: 0.99 there
  once meant 0.99%. The spec's `risk.*_drawdown` keys are **fractions**. The governance
  code (§7 phase B) reads only the fractions, and **raises** on any percent-named key
  holding a value below 1, which is ambiguous by construction.

### 2.8 Event budgets: per event, concurrency, clusters

With the event sleeve's budget b_E, K live slots, mean holding h̄ sessions, posterior
break rate q, and clusters of size m with within-cluster break correlation ρ_c:

- **Per-event size cap** (from the jump variance in §1.3, summed over a year of
  turnover):

  **x_max = b_E / [(g + ℓ)·√(K_eff·q(1−q)·252/h̄)]**, with **K_eff = K/(1 + (m−1)ρ_c)**

  Every input is measured from the event history, and none is chosen. ρ_c is set to
  1 unless ≥ N_clusters episodes show otherwise.
- **Cluster cap** (from the spec's drawdown lines, so it tightens as the book loses):
  - the loss if every live event in one cluster breaks at once, Σ_{e∈cluster}
    x_e·ℓ_e, must be ≤ **D_room = `risk.halve_drawdown` − current drawdown − ES21_cont**;
  - ES21_cont is the continuous sleeves' 21-session expected shortfall at 99%,
    measured. For the CEF book the worst 21-session loss on 2013–22 was 4.34% at
    6.5% vol [V §6.3].
  - Read as: a whole cluster breaking in the same month as a bad month for the
    continuous book must not take the book from where it stands to HALVE. If
    D_room ≤ 0, no new event opens.
- **Concurrency:** K_max = the smallest of:
  - the gross the allocator gave the sleeve ÷ the mean event gross;
  - the cluster caps;
  - the capacity caps per deal (§2.9);
  - any human-review throughput limit, if event extraction needs review
    (`EVENT_DRIVEN_POD` §6.1a).
- **No K_min top-up.** With few events live, the sleeve runs below budget. Inflating
  the per-event size to fill the budget is sizing on opportunity count, which is
  the dislocation-sizing family the graveyard killed (−12.9% at 35.8% vol in 2008;
  `docs/RESEARCH_STATE.md`). The unused budget returns pro rata to the continuous
  sleeves at the next review. That is the greedy rule `EVENT_DRIVEN_POD` §6.3 named
  as the control any learned allocation must beat.
- **Deal-break scenario per event:** recorded at entry as x_e·ℓ_e in NAV units, with
  ℓ_e the pre-announcement level of the spread (the "undisturbed" price), not a
  modelled one.

### 2.9 Capacity per sleeve

- **The pool is the auction the sleeve trades**, not ADV. An MOC book trades in a
  closing cross about 0.57% of the day's volume in these names
  [doc: EXEC_CAPACITY §2].
- **Measure each sleeve's participation in that cross** at the sizes its band or
  events actually trade. Use the notional-weighted median, because the band-edge
  trades carry the notional.
- The cap is the capital × vol-target product at which that participation reaches
  the team lead's P_max. Participation is linear in both.
- On ADV the CEF book reaches 1% of ADV on the median day's largest trade at
  **$1.49m** at 6%, a capital × vol product of **$0.089m-vol** [V §6.6]. Against the
  cross it binds already at $100k [doc].
- C4 reaches 1% of ADV at about $0.78m [doc: C4 §3].
- Per deal, the event sleeves' cap is the deal's own cross or ADV at the sleeve's
  participation limit, and that limit is set in each sleeve's pre-registration.

### 2.10 One account: netting, attribution, conflicts

- **One netted order per symbol** (`CLAUDE.md` landmine 2). The combiner sums every
  sleeve's target shares per symbol; the order is the net target minus the position.
- **Each sleeve keeps a virtual sub-ledger.** A fill is allocated to sleeves pro
  rata to each sleeve's signed target change in that symbol.
  - Internal crosses (one sleeve buys what another sells) trade nothing. Both legs
    are marked at the official closing print, which is fair to both and saves the
    cost. The saving is measured (§4.3).
- **Book-level constraints act on the net position, and the clamp is attributed.**
  - Example: an event makes a name restricted, with no new short under a NAV tender
    (C1). The restriction applies to the **net** position.
  - A sleeve whose target is clamped books the clamp as a transfer-coefficient loss
    on its own line. It is not hidden in the book's residual.
- **Flips** follow the runner's rule: close only, open next session. The flip is
  decided on the **net** position, so two sleeves can hold opposite views of one
  name without an order flipping.
- **Shortability** is checked on the net short that day (gate 7). A sleeve whose
  short is unbuildable sends nothing for it and records the shortfall. No other
  name is substituted.

### 2.11 When the allocation changes

- Budgets b_s change only at a scheduled **allocation review** (quarterly), or at a
  sleeve state change (admit, pause, kill).
- Inside a review each sleeve's own scalar runs daily, as today.
- Daily re-optimisation would trade estimation noise and pay for it twice: in cost,
  and in the sleeves' scalars chasing each other.

### 2.12 Evidence floor against capital budget

- Paper exists to produce live evidence, and is scored gross.
- A sleeve admitted on everything **except** the real-money cost gate may run on paper
  at an **evidence floor**: the smallest size at which whole-share rounding stays
  within the sleeve's declared tolerance on its smallest position.
- Its paper P&L is reported but never counted toward the book's absolute-return
  record, and it gets **zero** capital budget when capital arrives.
- This is a decision for the team lead (§8): it keeps the record honest without
  starving research of live data.

---

## 3. Risk

### 3.1 The factor model, book-wide

| factor | series (point-in-time; fetched by a repo fetcher) | why |
|---|---|---|
| equity | French `mktrf` (plus SMB, HML, RMW, CMA, UMD for the D4 set) | the alpha-only bar |
| credit | HYG − IEF total return (CRSP; `data/etf_daily.parquet` for live) | HY spread risk |
| rates / term | IEF − rf | duration |
| muni | MUB − IEF (CRSP) | the muni-vs-taxable bet |
| loans | BKLN − rf | floating-rate credit (JFR, and loan event names) |
| CEF discount | the equal-weight daily change in the CEF universe's discount (to be built from the panel, point-in-time) | the common discount component Lee, Shleifer & Thaler (1991) describe [S, `docs/REFERENCES.md` §1]; every CEF sleeve and every CEF event pair loads on it |

- **Returns-based exposure:** each sleeve's daily P&L (NAV units) on the factors,
  **Dimson-summed** (t and t − 1), HAC(5), over trailing 252 sessions. Book beta is
  the sum of sleeve betas: the P&Ls add.
- **Position-based exposure (ex-ante), daily:** each name's own trailing Dimson betas
  × today's net position.
- **Limit:** for each factor, |book β| scaled to the book's vol target ≤ 0.10. That is
  D4's bar applied to the whole book: alpha only, beta tolerated only as residual
  (team lead, 2026-10-09). Report it with its confidence interval:
  - point estimate over the limit with |t| < 2: an alarm, reviewed;
  - |t| ≥ 2 as well: a breach. The next review cuts the contributing sleeve.
  - **No hedge is added.** A hedge is a sized position and needs its own
    pre-registration. MUB, the natural muni hedge, was not shortable at Alpaca on
    2026-10-12 [doc: `docs/REFERENCES.md` §12i].
- **The baseline sits on that limit** (§6.4): Dimson rates β 0.102, scaled 0.094,
  t 1.50; alpha t 2.999.

### 3.2 Event-correlation clusters

A **cluster key** is attached to every position, continuous or event, so cluster
exposure is book-wide:

| key | example | why it clusters |
|---|---|---|
| sponsor | the 13 deployed names: **PIMCO 6** (PCN, PDI, PDO, PFN, PHK, PTY), **BlackRock 4** (BIT, HYT, MHD, MQY), AllianceBernstein, DoubleLine, Nuveen 1 each [V: `data/cef/cef_facts.csv` longName, fetched 2026-09-11] | one board, one distribution policy, one merger or tender programme (N8); MHD absorbed four BlackRock funds in 2026 [doc: EVENT_DRIVEN_POD §4.2] |
| acquirer group | merger-pair events | one acquirer, several targets |
| programme / regulator | a discount-management programme; an SEC rule or a court ruling that changes tender economics (the 2026 regime change in `docs/BRIEF.md` §3) | one decision moves every member |
| announcement wave | events announced in the same month | the waves are measured, not assumed (N8's base rate) |
| market stress | HY-stress state (worst quintile of 21-session HYG − IEF) | breaks and discount blow-outs coincide (2008, 2020) |

- **Sponsor net and gross are limited book-wide.** The limit is set at the review as
  a multiple of the book's vol budget: a sponsor's aggregate position must not carry
  more than its share of the cluster cap (§2.8). Measured daily.

### 3.3 Tail scenarios (a nightly read-only report on today's weights)

| scenario | how | baseline, last fit book [V §6.8] |
|---|---|---|
| 2008-09 → 2009-03 | fixed weights through the window; a missing name takes its group's mean that day (labelled) | DD 13.8% at 0.83× gross; **27.7% at the 1.80× cap**; long-only 19.0% |
| 2013 taper | same | 2.2% (cap 4.7%); long-only 7.3%; the policy itself drew down 1.7% |
| 2020-02-20 → 04-30 | same | 3.9% (cap 8.3%); long-only 16.9%; policy 3.6% |
| 2022-01 → 10 | same | 2.1% (cap 4.4%); long-only 10.2%; policy 2.7% |
| group-spread blow-out | today's net muni weight × the worst 21-session muni-minus-taxable move | worst move **−30.5%** (to 2009-04-07) and **+40.9%** (to 2009-03-09), checked against CRSP `ret` to three decimals. At the fit window's p95 net, 0.13, that is about **5.3% of capital** |
| every open event breaks | Σ x_e·ℓ_e, by cluster | — (no event sleeve yet) |
| every short recalled | longs held, shorts gone for the window | above |
| the 2021–22 borrow regime (P1) | the book's short book × the P1 fee for a year | the gate note's P1 row (−5.45%/yr at MOC on 2013–22) [doc] |

**The fixed-weight replays are the conservative case.** The live policy de-levers as
realised vol rises (63-session lookback), so in 2020 its own drawdown (3.6%) was close
to the fixed book's (3.9%). In a 2008-speed sell-off the 63-session window lags. The
13-name book's reaction to 2008 is **unmeasured** because it never traded it.

### 3.4 Drawdown governance and kill switches

Keep two kinds of stop apart. Mixing them is how a pre-committed kill rule gets
softened or graded early.

| | **risk stop (survival)** | **kill rule (evidence)** |
|---|---|---|
| question | can the book still be running in twelve months? | is the edge still there? |
| when it acts | any session | **only at the pre-registered horizon**: 60 live sessions for the CEF book, not before; no extension of rope |
| input | **broker-confirmed** equity (`equity.csv` on the VM), never a modelled session | the pre-registered statistic (spec `kill_rule`) |
| book level | HALVE at `risk.halve_drawdown` from the high-water mark: every sleeve budget × 0.5, so the vol target halves. KILL at `risk.kill_drawdown`: flatten every sleeve through the normal order path, write `ops/HALT_cef.md`, and require the team lead to restart | — |
| sleeve level | a sleeve's drawdown on its attributed line, **in units of its own budget** (DD_s/b_s). PAUSE (close-only, §3.5) when it passes the level its fit-period bootstrap reaches with probability ≤ p* over the review horizon: "this is not the backtested sleeve" | each sleeve's own H11 statistic at its own horizon (§4.1) |
| restore | **sticky**: HALVE stays until the team lead records a review, never automatically on recovery. Automatic re-levering whipsaws exactly when risk pays least (the strategy is best in calm markets, `docs/SYSTEM.md` §1) | a killed sleeve returns only through a new pre-registration |

**Why arm it now, on paper.** The justification for observe-only ("no real capital at
risk") was a justification on a clock. Real capital is planned (2026-10-09), and the
standing decision is to arm HALVE/KILL on broker-confirmed NAV (2026-09-08). The
deployed book's own fit drawdown of 12.78% would have triggered HALVE once in
2013–22 at 6.5% vol. That is what the line is for.

**Defects to fix when it is built** (found while writing; nothing changed here):

- `src/deploy/sleeves/cef_discount.py::risk_check` catches `Exception` and returns OK,
  which is a silent fallback. It also writes 0.18 and 0.12 as literals instead of
  reading the spec. The runner never calls it.
- Governance belongs in the runner, reading the spec through one units-checked
  reader. It does not belong in the sleeve.

### 3.5 Pausing one sleeve without touching the others

- **State lives in the book json, one key per sleeve**:
  `sleeves[i].state ∈ {active, close_only, flat}`. Absent means `active`, today's
  behaviour, with a byte-for-byte no-op proof (`CLAUDE.md`). The book json already
  lists `sleeves` with `enabled: true`, a key nothing on the Alpaca runner reads.
  - `close_only`: no position may grow. Reductions trade as the sleeve's targets
    ask. An event sleeve opens no new event, and live events run to their exits.
  - `flat`: the sleeve's target is zero in every name, and the combiner sends the
    netted reductions.

  This follows the `data.stale_nav` precedent: a runner setting in the book json, a
  reviewed edit of one key, reverted by deleting it. The *rules* (thresholds,
  budgets) stay in each sleeve's frozen spec.
- **Emergency pause without a commit:** a sleeve-scoped halt file,
  `ops/HALT_cef__<sleeve>.md`, read by the combiner as `flat` for that sleeve.
  - `ops/halt.py` today scopes by book only (`scoped_path(book)`), and
    `other_book_halts` would read such a file as another book's advisory halt. So
    the reader must be extended deliberately, with a test that the book-wide
    `ops/HALT_cef.md` and global `ops/HALT.md` still win.
- **Proof that the others are untouched:** a test that the other sleeves' targets
  and their netted orders are byte-identical with one sleeve `active`, `close_only`
  or `flat`. The netting may change the account's order in a shared symbol, and
  that is exactly the paused sleeve's own reduction.

---

## 4. Measurement

### 4.1 A live statistic and horizon per sleeve that would reverse it (H11)

| sleeve type | statistic | horizon | notes |
|---|---|---|---|
| the CEF book | the spec `kill_rule`: (a) live net Sharpe < 0; (b) slippage > 2× modelled for 5 consecutive sessions; (c) top-minus-bottom discount spread < 12% | 60 live sessions, **not before** | pre-committed; not softened here. The archived W6 note computed that (a) fires by chance often at 60 sessions (Lo's SE). That is a reason for **new** sleeves to pre-register a better-powered statistic, never a reason to edit this one |
| new continuous sleeves | the net Sharpe at its MinTRL horizon (computed in the pre-registration from the holdout Sharpe and moments), **plus** a cost clause that converges fast: mean implementation shortfall above the sleeve's breakeven at 95% over ≥ 20 sessions | MinTRL sessions; the cost clause from 20 sessions | cost converges far faster than Sharpe (`docs/BRIEF.md` research rules) |
| event sleeves | (i) mean net P&L per **resolved** event < 0; (ii) realised break rate above the posterior 95% upper bound; (iii) Brier score worse than the base-rate forecast | (i) N_clusters resolved, from §1.4. (ii) and (iii) at every resolution, but they **pause**, not kill | an event sleeve's horizon is in events, not sessions, and may be years. Say so in the pre-registration |

A sequential test (CUSUM or SPRT on daily P&L against the backtest distribution,
`EVENT_DRIVEN_POD` §6.4) runs beside each as **information only**. It never grades
before the horizon.

### 4.2 The three P&L lines, per sleeve

For each sleeve, from its virtual sub-ledger (§2.10):

1. **Alpaca's fill** (the official record), allocated to sleeves pro rata to target
   change;
2. **the official closing-auction print**: each sleeve's held shares marked at the
   print;
3. **distribution-adjusted**: line 2 plus distributions on each sleeve's shares at
   the start of each ex-date, credited long and charged short
   (`quantt/session/dist_score.py`, per sleeve).

Beside them, **labelled as modelled and never mixed in**: borrow at the measured fee
on each sleeve's attributed short. Paper charges none, and real capital will.

### 4.3 Attribution of the book's P&L

**Book P&L = Σ sleeve P&L (line 1) + crossing saving + residual.**

- The crossing saving is the cost the internal crosses avoided, at the measured
  cost per unit of turnover.
- The residual is fees, cash interest, rounding, and anything unexplained. It must
  be printed every day.
- **A residual above the measured noise of the fill allocation is a FAIL in verify**,
  because it means the attribution is wrong. Every sleeve's line is then suspect.

### 4.4 Turnover and cost budget

- **Each sleeve declares at admission:** its fit turnover per year, its breakeven
  cost per unit of turnover (net = 0), and its share of the book's cost budget.
- **The book's cost budget:** Σ_s turn_s × measured cost_s, less the crossing
  saving.
- **The live check:** the measured cost per unit of turnover per sleeve (TCA, by
  sleeve) against half its breakeven. Breaching it for 20 sessions moves the sleeve
  to `close_only` pending review.
  - For the CEF book, kill clause (b) already covers the extreme.
  - The breakeven is computed from data at the review (`REAL_MONEY_COSTS` §5 is the
    method), not copied.

---

## 5. The overview: a read-only portfolio dashboard

**Status: specification only.** `CLAUDE.md`: "the team lead will have a new one built
later", and "any monitor is read-only". Nothing below is built here.

**Where it runs and what leaves the VM.** Positions stay on the VM. Only counts,
ratios and verdicts leave it, as `ops.prod_state` already does. So:

- the risk report that feeds the dashboard runs **on the VM** after verify;
- it writes a summary of ratios, betas, shares and verdicts to the state directory;
- the dashboard reads that summary and orient.
- This repository is public: no account figure goes in a tracked file.

**Read-only by construction.** The dashboard module may import only from `ops/`
(orient, prod_state, halt readers) and a read-only Alpaca client. A test parses its
AST and fails on any call to `submit_order`, `cancel`, any `POST`/`DELETE`, or an
import of `quantt.session.run`.

| panel | what it shows | source (measured, never a document figure, H14) | if it cannot measure |
|---|---|---|---|
| **header** | prod machine, release tag, armed or dry, `DRY_RUN`, halts (global, book, sleeve) | `ops.prod_state`, `ops.halt.read_halt` | UNMEASURED, red |
| **equity and governance** | broker-confirmed equity, high-water mark, drawdown against HALVE and KILL (distance to each), **armed or observe-only**, the kill-rule session count against 60 | VM `equity.csv`; spec `risk.*` through one reader; verify's session count | red if unarmed |
| **sleeves** | per sleeve: state, budget b_s against ex-ante vol used, gross, net, names held, the three P&L lines (day, month, since inception), H11 progress (sessions or resolved events against horizon), uptime | the sleeve sub-ledgers; verify; `scores.csv`; `distribution_scores.csv` | that sleeve's row UNMEASURED |
| **live events** | event id, kind, symbols, state-machine status, `observed_at`, entry date, expected exit, size, break loss in % NAV, cluster key, days live; open events past their expected exit flagged | the event log (`EVENT_DRIVEN_POD` §3) | EVENTS_STALE if the EDGAR poll is older than its declared age |
| **risk budget** | ex-ante book vol (positions × trailing covariance), each sleeve's Euler contribution, σ* and which constraint binds, cluster caps used against D_room | the risk report | — |
| **breadth** | effective breadth on today's weights; the group bet's Euler share (muni-vs-taxable and four-group); top component share | the risk report (§6.5's method, on live positions) | — |
| **factor exposure** | returns-based and position-based book betas (equity, credit, rates, muni, loans, CEF discount), scaled to the vol target, against ±0.10, with t | the risk report | — |
| **stress** | the §3.3 replays on today's weights; all-events-break; all-shorts-recalled; group blow-out | the risk report | — |
| **concentration** | per name % NAV and % of shares outstanding; per sponsor net and gross; ownership thresholds (`EVENT_DRIVEN_POD` §7.2) | positions × a resolved share count | — |
| **capacity** | each order's share of the same day's closing (or opening) cross; days to exit each position at P_max | the auction prints verify already fetches | UNMEASURED for a non-NYSE venue until plan 0.2 maps it |
| **margin** | gross / NLV against `max_gross_stress`; Reg T initial and maintenance from the account; buying power; the netting benefit (Σ sleeve gross ÷ account gross) | Alpaca account (read-only) | — |
| **costs and borrow** | fill against the print per sleeve, cost per unit turnover against breakeven, shortable and HTB flags on held shorts, the short book's fee-weighted cost (modelled, labelled) | `tca.csv`; the probe snapshot; IBKR's public file | labelled stand-in or UNMEASURED |
| **data health** | panel last dates, stale-NAV gate verdicts, event-log freshness, factor-file vintages | orient PANELS; `nav_gate.csv` | — |

---

## 6. Zero-trial measurement now: the live book's own risk (fit window, pre-2023)

All from `python3 scripts/cef/portfolio_baseline.py` [V, run 2026-10-15]. The deployed
v7 policy is the one `real_money_costs.Book` builds (`band_gross_capped` on the 13
names, total returns, `evaluate()`), with first position 2013-06-25. Gross is the
headline and the cost grid sits beside it.

### 6.1 The book

| window | gross SR | ann % | vol % | turn/yr | net @5 | @15 | @30 | flips? | mean gross | mean short |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| live 2013-06 → 2014 | 1.30 | 7.33 | 5.65 | 16.3 | 1.15 | 0.86 | 0.43 | no | 1.20 | 0.59 |
| 2015–19 | 0.84 | 5.70 | 6.83 | 7.8 | 0.78 | 0.66 | 0.49 | no | 1.29 | 0.61 |
| 2020–22 | 1.02 | 6.49 | 6.36 | 21.5 | 0.85 | 0.51 | 0.01 | no | 1.07 | 0.54 |
| **live 2013-06 → 2022** | **0.96** | **6.21** | **6.50** | **13.5** | 0.85 | 0.64 | 0.33 | no | 1.21 | 0.58 |

This reproduces `REAL_MONEY_COSTS` §1 exactly (second method). Borrow is not in this
table; §6.7 charges it under labelled proxies.

### 6.2 Sizing, and return per unit of gross

- **The vol scalar**, on 2,397 live sessions:
  - mean **1.14**, median 1.12, p5 0.47, p95 1.97;
  - it never touched the 2.5 cap or the 0.2 floor.

  The "averaged 1.50, pinned at its cap on about 5% of days" figure is the 17-name
  book's [S, 2026-09-06], not v7's.
- **Held gross:** mean 1.21, median 1.26, p95 1.80; at the 1.80× cap on **7.3%** of
  sessions.

| window | vol % | σ₁ % (vol per unit gross) | σ₁ second method | vol at the 1.80 cap | gross for 20% vol | return per unit gross | at the cap | net 15bp per unit gross | at the cap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| live 2013-06 → 2014 | 5.65 | 4.70 | 4.69 | 8.47 | 4.25 | 6.09 | 10.95 | 4.05 | 7.29 |
| 2015–19 | 6.83 | 5.65 | 5.29 | 10.18 | 3.54 | 4.42 | 7.95 | 3.51 | 6.32 |
| 2020–22 | 6.36 | 6.08 | 5.96 | 10.95 | 3.29 | 6.08 | 10.94 | 3.06 | 5.51 |
| **live 2013-06 → 2022** | 6.50 | **5.65** | 5.39 | **10.18** | **3.54** | **5.15** | **9.27** | 3.47 | **6.25** |

### 6.3 Tails and drawdowns (daily, gross)

| window | skew | excess kurtosis | worst day % (in sd) | worst 5d % | worst 21d % | VaR99 % | ES99 % | max DD % | peak → trough → recovered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| live 2013-06 → 2014 | 1.51 | 7.7 | −1.43 (−4.0) | −1.38 | −2.43 | 0.63 | 0.94 | 4.49 | 2013-12-31 → 2014-06-30 → 2014-09-29 |
| 2015–19 | 1.69 | 11.7 | −1.82 (−4.2) | −3.46 | −4.34 | 1.04 | 1.26 | **12.78** | 2017-06-05 → 2018-06-12 → 2019-04-02 |
| 2020–22 | 0.21 | 13.7 | −2.71 (−6.8) | −3.12 | −3.17 | 1.02 | 1.67 | 4.32 | 2021-06-15 → 2021-08-11 → 2021-09-08 |
| **live 2013-06 → 2022** | 1.24 | **12.1** | −2.71 (−6.6) | −3.46 | −4.34 | 0.98 | 1.39 | **12.78** | as 2015–19 |

- **The five worst days:** 2020-02-27 −2.71%, 2020-03-12 −2.25%, 2020-03-18 −2.12%,
  2020-03-03 −1.82%, 2018-10-31 −1.82%.
- **The kurtosis 41.2 the desk quotes is the 17-name v5 book's**
  [S: spec `evidence.known_weaknesses`]. The deployed v7 book's excess kurtosis on
  2013–22 is **12.1**. That is still fat-tailed: the worst day is a 6.6-sd day. It is
  not the same number.
- **The longest drawdown took a year to trough and ten months to recover.** That is
  the horizon a 60-session kill review cannot see.

### 6.4 Factor exposure: the D4 test on the book itself

**W4's model** (FF5 + UMD + HYG−IEF + IEF−rf + MUB−IEF, contemporaneous, HAC(5)), live
window, reproduces W4 §6d exactly:

- alpha **5.88%/yr, t 2.87**;
- credit −0.021, rates 0.079, **muni 0.144** (W4: t 1.99);
- R² 0.011.

**The risk model** (Dimson, t and t − 1 summed, HAC(5)):

| window | n | alpha %/yr | t | equity β (t) | credit β (t) | rates β (t) | muni β (t) | loans β (t) | R² | max \|β\| scaled to 6% |
|---|---:|---:|---:|---|---|---|---|---|---:|---:|
| live 2013-06 → 2014 | 384 | 5.79 | 1.25 | 0.080 (1.38) | 0.079 (0.76) | 0.107 (0.82) | −0.061 (−0.58) | −0.234 (−1.00) | 0.040 | 0.249 |
| 2015–19 | 1,258 | 5.58 | 1.82 | −0.031 (−0.73) | 0.030 (0.42) | 0.113 (1.01) | 0.098 (0.69) | 0.073 (0.53) | 0.006 | 0.100 |
| 2020–22 | 756 | 6.56 | 2.07 | 0.005 (0.14) | 0.006 (0.11) | 0.107 (1.16) | 0.101 (0.95) | −0.060 (−0.91) | 0.074 | 0.101 |
| **live 2013-06 → 2022** | 2,398 | **6.10** | **2.999** | −0.003 (−0.13) | 0.030 (0.72) | **0.102 (1.50)** | 0.058 (0.74) | −0.047 (−0.93) | 0.018 | **0.094** |

**Downside credit** (the short-put shape): the Dimson β on min(HYG − IEF, 0) is
**−0.032 (t −0.85)**. The book does not lose more per unit of credit sell-off than it
gains per unit of rally. An event sleeve with deal-break risk will have that shape,
so the two do not compound in the tail through *this* channel; they may through
discount blow-outs (§3.3).

**Reading.**

- The factor R² is under 2%. Systematic risk is a rounding error in the book's
  variance.
- The alpha t straddles the 3.0 bar depending on the model: 2.87 / 2.999 here; 2.94
  daily FF5 + UMD and 3.22 monthly with Pástor–Stambaugh in W4 [doc].
- The rates beta sits at the 0.10 limit on a point estimate with t 1.5.
- So the book passes "not beta" and **narrowly misses** "alpha t ≥ 3.0" on daily
  data. Any sleeve that adds rates or muni beta pushes the book over the limit in
  §3.1.

### 6.5 Breadth and the group bet (ex-ante)

On 2,378 live sessions (20 skipped where a held name had no covariance yet; none
non-PSD), with h = the book decided at t and S = the trailing 252-session covariance
known at t:

| window | effective breadth, median (p10–p90) | top component share | names held | muni-vs-taxable Euler share, median (p90) | four-group Euler share, median (p90) | ex-ante vol % |
|---|---|---:|---:|---|---|---:|
| live 2013-06 → 2014 | 4.15 (2.72–5.99) | 39.4% | 10 | −0.1% (2.8%) | 13.8% (64.5%) | 5.89 |
| 2015–19 | 2.54 (2.07–4.88) | 56.8% | 10 | 3.2% (9.7%) | 21.4% (58.5%) | 6.06 |
| 2020–22 | 5.22 (2.70–6.33) | 31.1% | 10 | 5.4% (31.4%) | 16.8% (51.9%) | 5.28 |
| **live 2013-06 → 2022** | **3.48 (2.13–6.07)** | 42.9% | 10 | 2.4% (11.9%) | **20.1% (57.7%)** | 5.85 |

**Second method, realised:** the four-group spread P&L carries **30.4%** of realised
P&L variance on 2013–22 (25–40% by era), and earned +0.62%/yr of the +6.21%.

- **The net muni weight was zero on most fit sessions** (median |net| 0.000, p95
  0.130, max 0.311), because the ADV filter rarely admitted MHD and MQY then. W10-B
  found the same [doc].
- So the fit window **understates** today's group bet. The "92.5% on live weights"
  and "65.7% historically" figures are the 17-name book's, from
  `plan_diagnostics.py`. That script hard-codes the v6 17 names on purpose, and reads
  2021+ returns, which reach into the holdout years.
- **Today's v7 share is unmeasured here.** It is the first number the risk report
  must produce, from live positions on the VM.

### 6.6 Capacity (against 63-session ADV, at $100,000)

- **Coverage:** 4,324 name-trade-days on 1,080 trade days; none without an ADV.
- **Participation:** median **0.015%**, p90 0.156%, p99 0.553%, max 2.0%;
  notional-weighted median 0.149%. 0.12% of name-trades exceed 1% of ADV; none
  exceed 5%.
- **Each day's largest participation:** median **0.067%**, p90 0.294%.
- **Capital at which the median day's largest trade reaches a share of ADV**, at the
  6% target. The capital × vol product is the invariant.

| share of ADV | capital at 6% | capital × vol target | capital at 20% |
|---|---:|---:|---:|
| 1% | $1.49m | $0.089m-vol | $0.45m |
| 5% | $7.46m | $0.447m-vol | $2.24m |
| 10% | $14.91m | $0.895m-vol | $4.47m |

**Against the closing cross the same trades are roughly 175 times larger** (the cross
is about 0.57% of daily volume) [doc: EXEC_CAPACITY §2–§5]. That note measured
fit-period orders at a median 10.7% and notional-weighted median 52.5% of their own
day's cross at $100k [doc]. **For an MOC book the binding capacity is the cross, and
it already binds.**

### 6.7 Survival: P(touch the spec's lines within 252 sessions), the book rescaled

The lines are `risk.halve_drawdown` 12% and `risk.kill_drawdown` 18%, read as
fractions with an assertion. The run used 10,000 paths, seed 20261015. Each cell
gives SB21 / SB63 / Gaussian; the three are never averaged.

| series (live 2013–22) | Sharpe | P(DD ≥ 12%) at 6% | P(DD ≥ 12%) at 20% | P(DD ≥ 18%) at 20% | σ\*(12%, 5%) | σ\*(12%, 10%) | σ\*(18%, 5%) | σ\*(18%, 10%) |
|---|---:|---|---|---|---|---|---|---|
| gross | 0.96 | 0.1 / 0.2 / 0.8% | 54 / 53 / 72% | 15 / 15 / 31% | 10.1 / 9.4 / 8.0 | 11.7 / 11.3 / 9.4 | 15.5 / 14.5 / 12.4 | 17.9 / 17.5 / 14.5 |
| net 15bp | 0.64 | 0.3 / 0.6 / 1.6% | 62 / 58 / 79% | 22 / 18 / 40% | 9.1 / 8.5 / 7.2 | 10.5 / 10.6 / 8.5 | 14.0 / 13.1 / 11.1 | 16.1 / 16.3 / 13.0 |
| net 15bp + P3 borrow (today's fee level) | 0.53 | 0.4 / 0.8 / 2.1% | 66 / 62 / 82% | 25 / 20 / 43% | 8.7 / 8.2 / 6.9 | 10.0 / 10.1 / 8.1 | 13.4 / 12.6 / 10.7 | 15.4 / 15.5 / 12.5 |
| net 15bp + P1 borrow (2021–22 fee level) | −1.14 | **25 / 24 / 30%** | 98 / 98 / 98.5% | 88 / 85 / 88.5% | 4.4 / 4.1 / 4.1 | 4.9 / 4.7 / 4.6 | 6.8 / 6.4 / 6.4 | 7.6 / 7.3 / 7.1 |
| **zero edge** (gross, demeaned) | 0.00 | 1.9 / 2.8 / 6.0% | 84 / 81 / 90% | 46 / 39 / 59% | 6.9 / 6.6 / 5.8 | 7.9 / 7.8 / 6.7 | **10.7 / 10.2 / 9.0** | **12.2 / 12.0 / 10.4** |

σ*(L, p) is the largest annualised vol with P(max DD ≥ L within a year) ≤ p. The
Gaussian method gives the lowest, or tied-lowest, σ* in every row. The empirical
paths have positive skew (§6.3), which shortens drawdowns that a normal with the
same moments would extend. All three are reported; §2.6 uses the lowest.

### 6.8 Stress replays (fixed weights: the book decided 2022-12-30, gross 0.83×, net −0.077)

| window | name-days proxied by group | total % | max DD % | worst day % | max DD at 1.80× % | long-only max DD % | the policy's own DD % |
|---|---:|---:|---:|---:|---:|---:|---|
| GFC 2008-09 → 2009-03 | 584 | +6.98 | **13.80** | −4.45 | **27.72** | 18.99 | flat (never traded) |
| taper 2013-05 → 08 | 90 | −1.97 | 2.16 | −0.60 | 4.65 | 7.29 | 1.70 |
| COVID 2020-02-20 → 04-30 | 50 | +5.73 | 3.87 | −2.54 | 8.34 | 16.90 | 3.56 |
| rates 2022-01 → 10 | 0 | +1.53 | 2.05 | −0.72 | 4.40 | 10.23 | 2.70 |

The 2008 replay proxies BIT, DSL, PDI and PDO (not yet listed) by their group's
same-day mean, which is labelled and counted. The group-spread blow-out is in §3.3.

---

## 7. What has to exist in code, and in what order

Each phase is gated by the one before it. **P** = production (`quantt/`: a failing
test first, `/release-check`, a release tag, `install_vm`). **R** = research
(`scripts/`, never on the live path). No phase spends a trial. Each sleeve's own
trial is on its counter.

| phase | item | stream | spec / json keys (each absent = today, no-op proved) | done when |
|---|---|---|---|---|
| **A** (done here) | this framework; `scripts/cef/portfolio_baseline.py` and its tests | R | — | committed |
| **B: governance first** | 1. one units-checked reader of `risk.halve_drawdown` / `risk.kill_drawdown`; HALVE and KILL on broker-confirmed equity; sticky restore; `book_drawdown_suspend_pct` retired, or raising on a percent value below 1. 2. **`risk.controls_armed`** (absent = observe-only, today), then set true as the governance act recorded with the date. 3. the nightly **read-only risk report** on the VM (§5's risk, breadth, factor, stress, margin and capacity panels), ratios only. 4. the team lead states p* and P_max | P | `risk.controls_armed` | HALVE/KILL armed; the risk report runs nightly and prints today's group share |
| **C: the combiner** | the book json's `sleeves[]` read by the runner: each with `spec_path`, `budget`, `state`. `quantt/session/combine.py`: per-symbol netting, book-level restricted list on the net, flip on the net, virtual sub-ledgers, fill attribution, crossing saving, residual. Verify scores the three lines per sleeve and the residual. Sleeve-scoped halts. **No-op proof: a one-sleeve book gives the same orders, `plan_sha` and plan.json as today** | P | `sleeves[].state`, `sleeves[].budget` | the proof passes on the live spec, the real sleeve and the real panel, as the stale-NAV gate's did |
| **D: events** | the event log and `events_at(t)` with its runtime assertion (`EVENT_DRIVEN_POD` §3); entry and exit from event state; per-event and cluster caps in the gate (§2.8); the intraday subtract rule **only if the team lead approves it** (`EVENT_DRIVEN_POD` §2.3) | P + R | each event sleeve's own frozen spec | the first event sleeve's pre-registration names these caps |
| **E: the allocator** | `scripts/portfolio/allocate.py`: IR* (§2.3), R̃ (§2.4), the QP (§2.5), σ* (§2.6) with each constraint's value and shadow price; the W6 table on the **combined** book; `max_gross_stress` re-derived on the combined w5 at the promotion | R → P | the book json `allocation` block (budgets, review date) | two sleeves admitted |
| **F: the dashboard** | §5, when the team lead commissions it | P | — | — |

**The first second sleeve.** C4 is the only fit-pass candidate. Its holdout is shut on
three gates [doc: `C4_RESULT_2026-10-14.md` status]. Even if it passes:

- it **flips sign between 15 and 30bp** (net 0.247 at 15bp, −0.724 at 30bp, 38.1
  turns a year);
- its return per unit gross is about the book's, so on Reg T it adds Sharpe and
  breadth, not return (§2.5);
- its daily correlation with the book is 0.012, but 0.317 in HY stress [doc].

The allocator would give it weight by correlation alone until four sleeves exist.

---

## 8. Decisions for the team lead

1. **Arm HALVE/KILL now, on paper**, on broker-confirmed equity at the spec's 12% / 18%,
   with a **sticky** restore (your review, never automatic)? Recommended: yes.
2. **State p\***, the tolerated probability of touching KILL within twelve months.
   - The archived W6 prompt proposed 10%.
   - I recommend **5% on the zero-edge series**, the policy least sensitive to the
     edge we do not know.
   - For the CEF book alone that gives σ_kill ≈ 9.0–10.7%, about equal to the margin
     bound.
3. **Hold the vol target at 6%** until phase B is live, the cost gate passes or a
   borrow-aware short rule exists, and 20 armed Alpaca sessions with fills exist?
   Recommended: yes. The derived ceiling afterwards is about 9–10%, margin-bound.
4. **Sizing inputs:**
   - "fit for admission, holdout for size, live for kill";
   - net, never gross, for capital;
   - IRs ignored until four sleeves are admitted.

   Confirm.
5. **Sleeve state** in the book json (`sleeves[].state`) and **sleeve-scoped halt
   files**: confirm the design (§3.5).
6. **The evidence floor**: may a sleeve that fails only the real-money cost gate run on
   paper at the floor, excluded from the absolute-return record (§2.12)?
7. **Event caps**: the per-event cap from the sleeve budget, and the cluster cap from
   the room to HALVE less the continuous book's ES21 (§2.8). Confirm the use of the
   HALVE room.
8. **P_max**, the largest share of an auction cross the book may take, for real
   capital. The cross binds already at $100k [doc].
9. **Prioritise plan 4.2 (Portfolio Margin)?** On Reg T, gross binds the ≥10%/yr
   target before vol does (§0.1).

---

## 9. What is not established

- **No sleeve but the CEF book exists.** The allocator's inputs for any other sleeve
  are design, not measurement.
- **Every figure in §6 is in-sample to 2013–22.** The 2023+ holdout stays sealed. The
  CEF holdout was opened earlier and FAILED on net
  [doc: `docs/SYSTEM.md` §2, `pre-clean-slate:results/cef/HOLDOUT_OPENED.json`].
  *Correction, 2026-11-01 (CEF trial 53, Q7, team lead):* "the 2023+ holdout stays sealed" is not
  true of the core book. Its 2024-01-01 → 2026-07-30 returns were opened on 2026-07-31 (the line
  above). The v7 pre-registration computed the deployed book over 2013-06-14 → 2026-09-21
  (`results/cef/PREREG_ALPACA_V7_2026-09-28.md` §5). Treat the core's 2023+ as seen. This note's
  §6 figures are unaffected: they are fit-only.
- **The bootstrap rescaling assumes the Sharpe is invariant to size.** Costs per unit
  turnover rise with participation, which is unmeasured at auction.
- **Today's live group share, live factor betas and live margin cushion are
  unmeasured here.** They need the VM's positions (phase B's risk report).
- **The 13-name book's behaviour in 2008 is unmeasured.** It was flat.
- **Survivorship** (`docs/SYSTEM.md` §2): unmeasured, and biased upward.
- **The CEF discount factor** (§3.1) is designed, not yet built.

**Found while measuring (not changed here):**

- **A live-path test now fails on this machine because of the data, not the code.**
  `quantt/session/tests/test_nav_gate.py::test_real_sleeve_on_the_real_panel_report_mode_is_byte_identical`
  pins the reviewer's PDI case on "the real panel as captured 2026-09-28". The shared
  `data/cef/cef_nav.parquet` was refreshed at 16:24 on 2026-10-15, and the refresh
  corrected exactly those stale copies: PDI 2026-09-25 went from 15.06 to 15.10, DSL from
  11.11 to 11.10. The old file is beside it as `cef_nav.parquet.pre-20261015.bak`. This
  branch touches nothing under `quantt/`, `src/` or `ops/`. The fix is a frozen copy of
  the panel for that test, as trial C5 did for its fit. It is a live-path test, so the
  fix goes through `/release-check`.
- `plan_diagnostics.py`'s PCA (the source of the 65.7% / 92.5% group shares) reads
  2021+ returns, into the holdout years, on the v6 17 names (§6.5).
