---
name: combine
description: Rebuild the combined-book proposal from the current paper and shadow sleeves - each sleeve's forecast and confidence, shrinkage toward equal-risk weights, a penalty on correlated sleeves, the risk target and leverage, regime scaling, and the capacity table. Use for the weekly combined-book review or when a sleeve joins or leaves. A proposal only; it changes no book.
---

# Combine: the combined-book proposal

`docs/MISSION.md` §6 and the 2026-11-09 ruling (`docs/SYSTEM.md` §5): move
toward one combined alpha model. The seat is `portfolio-architect`.

## 1. Inputs, measured now

- The sleeves: the books on `/scoreboard`, and the `PAPER` and `SHADOW` rows of
  `results/IDEA_LEDGER.md`. Until the paper/shadow runner exists these are the
  core and C4 books only; say so, and treat any Explore-stage sleeve as a
  labelled backtest input, never as a paper record.
- Each sleeve's per-period P&L: broker-confirmed for paper, labelled simulated
  for shadow, labelled backtest for Explore. Never mix the three in one column.
- Live parameters from the frozen specs (`scripts/cef/spec.py`,
  `python3 -m ops.orient` SPEC), never as literals.

## 2. The model

1. **Forecasts.** Each sleeve gives an expected return and a confidence, not a
   weight.
2. **Shrinkage toward equal-risk weights.** State the shrinkage and derive it
   from the length of the records: short records shrink hard.
3. **Correlation penalty.** Estimate the sleeve correlation matrix with ranges;
   two sleeves that are one bet share one bet's risk.
4. **Risk target.** Size the whole book to a volatility target the paper record
   supports. State the target, the leverage it implies and why. More risk is
   acceptable where the evidence supports it.
5. **Regimes.** If risk scales by regime, the regime on a date uses only data
   available on that date (`market-historian-economist`).

Arithmetic helpers: `marginal_gain` and `combined_sharpe` in
`scripts/research/inference.py`.

## 3. What the proposal shows

| block | content |
|---|---|
| sleeves | status, record length, gross Sharpe, exposures |
| correlation | the matrix, with ranges |
| weights | equal-risk, the shrunk combination, and the difference |
| contribution | each sleeve's contribution to return, risk and drawdown |
| capacity | per sleeve and combined: position size against ADV at $1M, $5M and $10M |
| risk | the target, leverage, concentration and liquidity limits |
| controls | which gates act and which only report, and any proposal to change one |
| retire | sleeves that have stopped adding value, with the evidence |

Results are gross. Measured costs appear only for a sleeve in a go-live
proposal.

## 4. Where it goes

A dated note under `results/mission/`, an entry in
`results/report/EVIDENCE_LOG.md`, and the decisions put to the team with a
recommendation and the alternatives.

**It changes nothing by itself.** Reworking the core or C4 book is done on paper
first; a frozen-spec key goes through `/spec-change`; a prod release is the team
lead's alone.
