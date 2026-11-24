---
name: explore
description: Run the Explore stage on one idea card - the fast gross test on the canonical harness, one early/late time split, at least two regimes, exposures, the capacity table, a code review, and the ledger line. Use after /idea, or to re-test a set-aside idea with a new angle.
argument-hint: <slug>
---

# Explore one idea

Slug: **$ARGUMENTS**. The card is `results/ideas/YYYY-MM-DD_<slug>.md`. If there
is none, write it first (`/idea`).

The saved workflow `research-idea` runs these steps with separate agents. This
skill is the same procedure for one session.

## 1. Data

- The data card exists (`data-scout`): source, coverage, last date, publication
  lag, lookahead plan.
- The series is audited (`data-analyst`): coverage, stale prices, bad bars,
  alignment, survivorship. **State each panel's last date.** A stale panel is
  reported as stale, never used silently.
- Research output is written outside `data/` (`CLAUDE.md` landmine 9).

## 2. The gross test

Use `/harness`. `scripts/research/harness.py` is the one backtester.

- Build a daily target-weight panel (`cross_sectional_weights`, `event_weights`,
  or the CEF builders).
- Close-traded signals: `shift(2)` through `harness.evaluate`. Another fill is
  stated and asserted.
- Assert no lookahead; run `harness.truncation_check` on a new builder.
- Gross only. No cost, borrow or slippage assumption.

## 3. What the result shows

| block | content |
|---|---|
| headline | gross annualised return, volatility, Sharpe, maximum drawdown, hit rate, turnover a year |
| time split | the same row, early and late |
| regimes | the same row in at least two market regimes, the label built only from past data |
| exposures | betas to equity, rates and credit; correlation with the sleeves held (`beta-detector`). Reported, not a veto |
| capacity | position size against ADV at $1M, $5M and $10M |
| control | the row where the effect should be absent |
| chart | one equity curve |

Every figure labelled `[V]`/`[S]`/`[U]`. Where windows overlap or events
cluster, the standard errors come from `scripts/research/inference.py`
(`statistician`).

## 4. Code review

`quant-reviewer` reads the script: lookahead, leakage, silent fallbacks, units,
alignment, stale prices. A correctness finding is fixed and the test re-run
before the result is written up.

## 5. Write it up, in one commit

- A short note under `results/<family>/<slug>/` with the table, the chart, the
  reproducing command and the panel dates.
- **One line in `results/IDEA_LEDGER.md`**: date, idea, data (last date), gross
  result, status.
- An entry in `results/report/EVIDENCE_LOG.md` (`.claude/rules/report.md`).

## 6. What next

The Explore bar (`docs/MISSION.md` §7): a gross effect with a sensible sign and
size, that holds in both halves or has a clear regime story, with no lookahead,
tradeable at the stated capital.

- **Clears it:** status `EXPLORE`, and `/paper <slug>`.
- **Does not:** say plainly what it showed and which angle was not tried. Name
  the next tweak with its reason, or mark it `SET ASIDE` with what would reopen
  it. One failed check does not end an idea; a re-test is another line in the
  ledger.

## Rules

No order is sent. No panel under `data/` is written. No figure is recalled.
