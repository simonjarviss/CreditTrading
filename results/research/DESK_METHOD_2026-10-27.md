# The research method, and why the desk's research ends NO GO — 2026-10-27

**Zero trials. No counter moved, no spec changed, nothing on the live path.**
Branch `desk-research-method`, cut from `origin/main` at a8c3720.
Reproducers (`scripts/research/inference.py`): `python3 -m scripts.research.inference bars 52 --years 13 --sr 0.67`
(§4) and `python3 -m pytest scripts/research/tests -q` (§5). The audit in §2
reads the notes it cites, on the branches named.

## 0. The question, and the short answer

The team lead asked for agents for quantitative research, quantitative trading,
data analytics, data gathering, ML model implementation and statistics, "and
anything else to do proper scientific quantitative research … we aren't using
proper method and it's why all our research turns into NO GO". They chose to
**rebuild the desk** rather than add seats beside it, to **upgrade
`research-idea`**, and to land the work on a new branch with a PR.

The claim was tested against the record before it was acted on (§2).

- **As stated, it is not supported.** Most kills are sound. 29 of 82 were
  correct kills: artifacts, controls that scored as well, powered nulls. 26
  were honest implementation blocks.
- **It is supported where it matters most: the counted trials.** Four of the
  seven counted-trial kills since 2026-09-28 (C5, E1, NAV tenders, X3) had a
  real gross effect that beat its own control or placebo.
  - Each was then killed by a gate that its own pre-registration forecast it
    would probably fail.
  - Or it was judged standalone, or recorded with a code saying the effect
    does not exist.
- The method failures are specific, and none of them is "too little rigour":
  1. power computed and then ignored;
  2. verdicts that name the gate, not the evidence;
  3. a passing component dying with a failing expression;
  4. sleeves judged alone;
  5. a bar stricter than the method it cites.

## 1. What was done

| step | what | provenance |
|---|---|---|
| deep research | 104-agent `deep-research` run: 5 angles, 22 sources fetched, 95 claims, 25 verified by 3-vote adversarial check (23 confirmed, 2 refuted) | the session's workflow journal; key sources in `docs/REFERENCES.md` §12rm |
| gap fill | The run's ML (area 3) and signal-combination (area 4) claims never reached verification. López de Prado's "10 Reasons" was then read in full (pdftotext of the GARP-hosted PDF), with the Gu–Kelly–Xiu NBER abstract and the Clarke–de Silva–Thorley FAJ abstract | §12rm |
| audit | a zero-trial read of every killed / NO GO / INFEASIBLE / MIXED idea in `docs/RESEARCH_STATE.md` and the `results/` notes on `main`, `simon` and the `trial-*`/`research-*` worktrees | §2; four load-bearing citations re-read by hand [V] |
| inference module | `scripts/research/inference.py`, tested (`scripts/research/tests/`) | §4 |
| the desk | 11 seats replacing 8 (and absorbing two unmerged SS seats); `research-idea` rebuilt | §5 |

## 2. The audit: 82 ideas, classified

Each kill was classed by what the test **could** show. Where a note reported an
SE (or an effect and its t), the minimum detectable effect at 80% power and 5%
two-sided is ≈ 2.8 × SE, compared with the cost hurdle or the size that would
matter.

| class | count | meaning |
|---|---:|---|
| CORRECT KILL | 29 | 15 before the clean slate, 14 since: an artifact or control failure shown directly, or a powered null |
| IMPLEMENTATION | 26 | borrow, shortability, costs, data access; all honestly labelled |
| UNDERPOWERED | 20 | could not have detected a meaningful effect; 15 are count gates labelled D7 |
| STANDALONE | 3 | judged alone where its value is as a diversifier or conditioner (plus 4 where it is secondary) |
| PROCESS ERROR | 1 | C5 |
| UNCLEAR | 3 | |

**The counted trials since 2026-09-28** (figures as read by the audit from the
cited notes [S]; the four marked [V] were re-read by hand on 2026-10-27):

| trial | gross effect | what killed it | what it shows |
|---|---|---|---|
| C5 (CEF 51) | G +293bp/yr, t 2.82; holdout +313.6bp/yr, t 4.66 | lagged-signal placebo split: G − G_lag −58bp/yr, t −0.56 (MDE ≈ the whole gain) | labelled **D1** although the gain replicated. The placebo split was INCONCLUSIVE, not ABSENT |
| E1 (EVENTS 1) | muni pair median +167.4bp, t 2.79; controls +12.0 / +68.9bp [V] | D4 alpha t 1.90 < 3.0, with max \|Σβ\| 0.021 [V] | the pre-registration forecast P(alpha t ≥ 3) ≈ 0.28 and P(DSR pass) 0.15 [V]. A **power** failure labelled as a risk premium |
| NAV tenders (EVENTS 2) | +1.084%/event, t 2.80; A−B +0.634%, t 3.27 | net@15 t 1.53 < 2.0; D4 t 1.92; DSR 0.39 | the pre-registration forecast P(DSR) 0.02 at SR 0.4 [V]. Correlation with the book 0.086, never weighed |
| X3 (XASSET) | SR 1.04, t 4.94; alpha t 4.54 | D4 on TERM β 0.34 | detected. The hedged expression was never run |

Sources:
- C5: `results/cef/C5_RESULT_2026-10-14.md`.
- E1: `results/events/E1_RESULT_2026-10-22.md` and
  `PREREG_E1_MERGER_PAIR_2026-10-19.md`, both on branch `trial-events-e1`.
- NAV tenders: `results/events/NAV_TENDER_RESULT_2026-10-20.md` and
  `PREREG_NAV_TENDER_2026-10-19.md`.
- X3: `results/xasset/XASSET_RESULTS_2026-10-14.md`.

The admission rule was re-read too [V]:
`results/cef/PORTFOLIO_FRAMEWORK_2026-10-15.md` §2.1 admits a sleeve only after
a standalone deflated Sharpe at the counter's N and the D4 test.

### The five process gaps the pattern shows

1. **Power forecast, then ignored.** NAV tenders P(pass) 0.02, E1 0.15–0.28,
   XASSET needing SR 0.95–1.12 for 80% power. X5 was withdrawn on power before
   any data, which proves it can be done. The others ran anyway.
2. **The D5 "inventory" principle is never applied.** Admission needs a
   standalone DSR plus alpha t ≥ 3.0, so the allocator's own marginal bar
   (IR > ρ·IR_c) never sees a sleeve that fails standalone. Affected: NAV
   tenders, E1, G2, X4, S3-forced-flow, A1.
3. **D-codes name the gate that fired, not what was found.** C5 is labelled D1,
   E1 D4 (no beta to speak of), X1 D1 (spanned, D4 in substance). With "never
   re-test without new data", a wrong D1 buries an effect for good.
4. **A passing component dies with its expression.** None of these has a
   successor entry: X3 hedged against TERM, NAV tenders' A−B payoff, C5 as an
   execution choice, A1 as a conditioner, G2 held to expiry.
5. **Conservative cost conventions decide what is recorded as an alpha
   verdict.** G2 was judged on the stacked upper-bound cost row, although its
   point-cost net has t 3.35.

## 3. What the literature says (verified 2026-10-27)

| finding | confidence | sources (§12rm) |
|---|---|---|
| **Team design.** López de Prado: lone researchers each owning a strategy (the "Sisyphus paradigm") end in overfit backtests or crowded factors. Every successful firm he knows runs a "meta-strategy" assembly line, with subtasks measured independently. *This is first-person experience, not data* | medium | "10 Reasons" (read in full) |
| **Backtesting is not a research tool.** About 20 iterations of backtest-and-tweak find a false strategy at 5%, walk-forward included. Research through cross-validated feature importance, and keep the backtest as a final check | high | "10 Reasons" #2; Arnott–Harvey–Markowitz 2019 |
| **Type II error is a cost.** Tests that control only false positives can miss most true effects: in Harvey & Liu's double bootstrap, a standard test missed in 86.9% of trials. No fixed hurdle is optimal. Calibrate it to the data and a prior; on their data a 5% FDR needed t 2.4, not 3.0 | high | Harvey & Liu 2020 |
| **Effective trials.** N in the DSR is the number of *independent* trials. Counting correlated variants raises the bar and rejects true effects. N̂ = ρ̄ + (1−ρ̄)M | high | Bailey & López de Prado 2014; AHM 2019 |
| **√(2 ln N) is an upper bound** on the expected best-of-N, to be scaled by the measured cross-trial Sharpe spread | high | "10 Reasons" #10; Bailey & López de Prado 2014 |
| **Low-Sharpe power.** A true Sharpe of 0.5 needs about 43 years for 99.9% significance, and has 61% power over 20 years at 5% | medium | Rej, Seager & Bouchaud 2018 |
| **Event-study power** falls with the window length and with volatility: N ≈ ((z+z)·σ·√L/AR)². Cross-correlated events understate the SE by √(1+(n−1)ρ), making false positives; calendar-time portfolios avoid it | high | Kothari & Warner 2007 |
| **PBO by CSCV** replaces a single hold-out for selection among configurations. It needs every trial's P&L series | medium | Bailey, Borwein, López de Prado & Zhu |
| **ML on financial data:** triple-barrier labels; meta-labelling over a white-box primary; uniqueness weights; purging and embargo; combinatorial purged CV | high (one primary text) | "10 Reasons" #5–#9 |
| **ML gains need a large cross-section.** Trees and neural networks win from nonlinear interactions, on a very large US stock panel | medium | Gu, Kelly & Xiu 2020 (abstract) |

**Not verified, and not relied on:** the Grinold–Kahn / Clarke–de Silva–Thorley
formula IR = TC·IC·√BR and its "TC 0.3–0.8" (the abstract page does not carry
them; they stay [S]); named FDR procedures beyond BH; Bayesian shrinkage. The
marginal-Sharpe rule SR_k > ρ·SR_book is algebra, derived in
`inference.marginal_gain` and pinned by a test.

## 4. The desk's own bar, measured

`ops/orient.py` and `scripts/cef/validate.py::_dsr` derive the bar as √(2 ln N)
on the raw counter. They set the cross-trial variance to the null sampling
variance 1/T, so V[SR_n] is never measured. Measured 2026-10-27 with
`python3 -m scripts.research.inference bars <N> --years 13 --sr 0.67`:

| counter (main, 2026-10-27) | N | desk bar | Gumbel E[max] | P(DSR > 0.95), true SR 0.67 over 13y: desk / Gumbel |
|---|---:|---:|---:|---|
| CEF | 52 | 2.811 | 2.291 | **0.021** / 0.064 |
| EVENTS (declared) | 6 | 1.893 | 1.300 | 0.131 / 0.298 |

- A second session re-derived the CEF row independently with scipy and got the
  same 0.021 and 0.064.
- These are dated observations, not inputs (H14). Re-run the command at the
  counter's current N.
- **What it means:** at the CEF counter's N, a genuinely good new CEF sleeve
  fails the gate about 98 times in 100. The bar is set by a cited method, but
  set more strictly than that method, in two of three ways (the upper bound,
  and the raw N).
- Which bar gates is a counter-regime decision for the team lead (§7).

## 5. What changed on this branch

**The desk** (`.claude/agents/`). It is one research line; `.claude/README.md`
has the map.

| station | seat | the team lead's word | absorbs |
|---|---|---|---|
| 1 | `quant-researcher` | quantitative research | alpha-finder, unique-angle-researcher |
| 2 | `data-engineer` | data gathering | data-librarian (on `simon`) |
| 3 | `data-analyst` | data analytics | new |
| 4 | `statistician` | statistics | event-econometrician (on `simon`) |
| 5 | `ml-engineer` | ML model implementation | new |
| 6 | `backtest-engineer` | the backtester | the old workflow's anonymous Test stage |
| 7 | `beta-detector`, `quant-reviewer` | adversaries on the claim and on the code | rewritten |
| 8 | `portfolio-manager` | portfolio oversight | rewritten; now judges marginal contribution |
| 9 | `quant-trader` | quantitative trader | execution-trader |
| — | `market-structure-analyst` | domain, consulted by every station | equity-research |

The four SS domain seats on `simon` (`event-scout`, `filings-analyst`,
`deal-analyst`, `credit-situations-analyst`) are unaffected. **When `simon`
merges, delete its `data-librarian.md` and `event-econometrician.md`.** Their
content is in `data-engineer` and `statistician`, and `ops/doc_audit.py` will
report any seat on disk that CLAUDE.md does not name.

**`research-idea`** (`.claude/workflows/research-idea.js`) now runs in two
stages:
- **Design** (Screen → Data → Power → Pre-register) spends nothing. It stops
  if P(pass) at the binding gate is below 0.5, unless the team lead overrides.
- **Test** refuses to start without `{prereg, approved: true}`.

This fixes a defect: the old version ran the test straight after drafting the
pre-registration. Nothing in it waited for approval, although its `whenToUse`
said otherwise. Every verdict now carries the evidence outcome (PRESENT /
ABSENT / INCONCLUSIVE) beside the D-code, the standalone and marginal
readings, and a successor entry for a PRESENT effect whose gate failed.

**`scripts/research/inference.py`**: one tested implementation of power, MDE,
event counts, both DSR bars, effective trials, PSR, P(pass), Newey–West, BH,
PBO/CSCV, `read_result` and the marginal-Sharpe arithmetic.
- Each formula reproduces its paper's worked example: DSR 0.9004, Sharpe power
  0.609 / 0.146, Kothari–Warner's 21 events.
- `desk_dsr` and `newey_west_t` match `validate._dsr` and `vrp_summary` to
  1e-12, so moving a trial onto it changes no past number.
- Kothari–Warner's 60-event figure for the top volatility decile is *not*
  reproduced by their formula (58.5), and is not pinned.

**Reviewed before commit.** An independent `quant-reviewer` pass on the module
and the workflow found these, all fixed on this branch:
- `combined_sharpe` could never say no, because the unconstrained optimum shorts
  a weak sleeve;
- `read_result` ignored the trial count;
- `p_pass_dsr` assumed normal returns;
- the default bars differed between `dsr` and `p_pass_dsr`;
- `newey_west_t` accepted impossible lags;
- the PBO tests could not catch a wrong rank;
- in the workflow: a null agent result read as a clean one, `min_power: 0`
  silently disabled the gate, the gate trusted one reported number, and the
  pre-registration was not pinned to a commit.

Each fix has a test, or a stand-in workflow run, that fails on the first
version.

**A drift found in passing.** The old `beta-detector` restated the D-legend with
different meanings from the canonical one in `docs/RESEARCH_STATE.md`:
- its D3 was "not implementable", where the canonical D3 is "great in old
  data, bad in new";
- its D5 was "opportunity count collapsed", where the canonical D5 is
  "Sharpe 0.3–0.6, keep as inventory".

The desk had been labelling kills from two legends. The new seats point at the
canonical legend and restate none of it. `.claude/rules/research-harness.md`
also paraphrases D7 differently ("infeasible on the available data" against
"fewer than ~250 independent trades"). It is left for the team lead's ruling.

## 6. What this does not do

- **The new seats load only in a new Claude Code session.** Neither they nor the
  rebuilt workflow have been run end to end. The first `research-idea` run is
  their test.
- **No past verdict is changed.** The relabels and re-opens in §7 are proposals.
- **The harness restructure and the ML pipeline** (purged CV, CPCV,
  triple-barrier, uniqueness weights → positions → harness) are not built here.
  The team lead gave them to another session on 2026-10-27. Those seats follow
  whatever `CLAUDE.md` says at run time.
- **Trial P&L series do not exist for past trials.** Effective N, V[SR_n] and
  PBO cannot be computed for the 52 CEF trials until they are rebuilt or
  backfilled.

## 7. Decisions for the team lead

> **Ruled 2026-10-27** (`docs/SYSTEM.md` §5): 1 the paper's bar once series exist; 2 workflow only; 3 yes, paper only; 4 yes, add and relabel; 5 all four re-opens queued, in the order listed; 6 backfill what is reproducible.

1. **Which DSR bar gates.** The desk's (√(2 ln N), raw N), or the paper's
   (Gumbel, effective N, measured V[SR_n]). Report both meanwhile. *Recommended:*
   the paper's, at effective N, once trial series are stored; until then, both
   are shown and the desk's gates.
2. **Make the power gate a written rule.** No trial is spent when P(pass) at the
   binding gate is below 0.5 at a cited plausible effect. Today only the workflow
   enforces it. *Recommended:* add it to `CLAUDE.md`'s research rules.
3. **Admission by marginal contribution.** Allow a sleeve that fails the
   standalone DSR but adds to the book (SR_k > ρ·SR_book with ρ's range, net
   positive across the grid) into the paper book, labelled as such.
   *Recommended:* yes, for paper only. Real capital keeps the standalone gate.
4. **Record the evidence outcome beside every D-code** in
   `docs/RESEARCH_STATE.md`, and relabel:
   - C5 (D1 → PRESENT, placebo INCONCLUSIVE);
   - E1 (D4 → alpha INCONCLUSIVE);
   - X1 (D1 → spanned).
5. **Zero-trial re-opens** (the audit's list):
   - C5 as an execution decision, with s_open re-measured on 2023–26 quotes;
   - NAV tenders and E1 judged on their marginal contribution to the book;
   - A1 as a conditioner;
   - G2's two named inputs;
   - X3 hedged against TERM: a power check first, since its holdout is spent;
   - MA-HZ on the 2001 census.
6. **The trial ledger.** From now on every trial stores its per-period P&L
   series. Decide whether to backfill the CEF trials.

## Reproduce

```bash
python3 -m pytest scripts/research/tests -q
python3 -m scripts.research.inference bars 52 --years 13 --sr 0.67
python3 -m scripts.research.inference power --sr 0.5 --years 20
```
