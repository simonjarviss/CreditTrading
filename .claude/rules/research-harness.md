---
paths:
  - "scripts/**"
  - "src/backtest/**"
---

# The research harness

These are the rules every piece of research inherits. **Rewritten 2026-11-09**
to the team lead's ruling of that date (`docs/SYSTEM.md` §5; `CLAUDE.md`, "Hard
rules — research", is the authority). Research is judged on gross signal and
paper trading is the filter. Retired for research: the cost grid and borrow
haircuts (formerly H3, H4), turnover-matched net comparisons (H2), "no sweeping
and picking" (H8), the untouched-names and time-holdout ceremony (H9, H13), the
trial counters and their bars (H10), pre-registration (H11), and the
factor-exposure kill. `docs/BRIEF.md` §5 still carries the older H1–H15 text;
where it differs, `CLAUDE.md` wins.

**Do not build another backtester.** The canonical one is
`scripts/research/harness.py` (`band_frontier.evaluate` delegates to it,
byte-identical on the live book). Extend it visibly, with a test:

```python
from scripts.research import harness        # EXEC_LAG, evaluate, report, the family builders
H   = harness.cross_sectional_weights(signal, eligible, ...)   # or event_weights(...)
res = harness.evaluate(H, R)    # applies H.shift(harness.EXEC_LAG)
rep = harness.report(H, R)      # full, early/late (its fit and holdout rows), eras
# the CEF sleeve: scripts.cef.band_frontier build_targets / band / evaluate, parameters from scripts.cef.spec
# ML: scripts/research/ml.py; standard errors: scripts/research/inference.py
```

`harness.report` still returns net-of-cost columns from before the ruling. Do
not put them in a research table.

## What stays

**H1. Execution convention is `shift(2)`** for anything traded at the close.
Decide at *t*, MOC fill at *t+1*, earn the *t+2* return. `validate.py` once used
`shift(1)` — entering at day *t*'s close on day *t*'s NAV, which publishes after
that close (`pre-clean-slate:results/cef/EXECUTION_CONVENTION_2026-09-10.md`).
A sleeve with a different fill (an open, an intraday window) states its
convention in a comment and asserts it.

**H5. Eras: 2005–09, 2010–14, 2015–19, 2020–22, 2023–26**, where the sample
allows. Pre-2013 is thin on the CEF panel.

**H6. IC** is Spearman between the signal at *t* and the forward return starting
*t+2*, **non-overlapping**, standard errors **clustered by date**, never naive.

**H7. No lookahead, including in the data.** A signal uses only what was
available at decision time: NAV publication lags, filing and acceptance dates
and never period ends, index membership as of that day, macro data at its
first-release vintage, regime labels fitted on past data only. State the
alignment in a comment. Assert it at runtime. `src/backtest/guard.py` and
`harness.truncation_check` exist for this.

**H12. One control.** If a mechanism says an effect lives in munis, test it in
high yield too. If it is equally strong where the mechanism cannot operate, it
is not what you think. This is a bug check, not a gate.

**H14. No decision rule may key on a number written in a document.** Every
figure in the docs is a starting observation with a date and a method. The test:
*could this rule still be executed correctly by someone who deleted every number
from the document?*

**H15. Returns are total returns.** If the distribution panel cannot cover a
name-date, the harness **raises**; it never falls back to price returns silently.

**No silent fallbacks.** Never `except: pass`, never `fillna()` an invented
value, never a default for missing data. Raise, naming what was missing.

**No invented numbers.** Every figure is fetched or computed and labelled `[V]`,
`[S]` or `[U]`, with the panel's last date.

## What every result shows

1. **Gross headline**: annualised return, volatility, Sharpe, maximum drawdown,
   hit rate, turnover a year. No cost, borrow or slippage adjustment.
2. **One time split**: the same row for an early and a late period.
3. **At least two market regimes**, the label built only from past data.
4. **Exposures**: betas to equity, rates and credit, and the correlation with
   the sleeves already held. Reported, never a veto.
5. **Capacity**: position size against average daily volume at $1M, $5M and
   $10M. Feasibility, not a cost.
6. **The control's row**, one equity-curve chart, the reproducing command, and
   each panel's last date.

Parameters may be explored; show the neighbours of the value chosen.

## The record

**One line in `results/IDEA_LEDGER.md` per idea tested, in the same commit**:
date, idea, data, gross result, status. It is a record, not a gate. Log the
result in `results/report/EVIDENCE_LOG.md` too.

## Where output goes

Research output goes under `results/`, and research data into a research data
folder. **Never write under `data/`**: the live sleeve decides on it
(`CLAUDE.md` landmine 9). Nothing under `quantt/` or `src/deploy/` imports a
research data source.

## Reading older results

Verdicts written before 2026-11-09 use the codes D1–D7 (the legend is in
`docs/RESEARCH_STATE.md`, frozen as history). D2 (stopped on costs) and D4
(stopped on factor exposure) no longer end an idea: a row with a positive gross
effect is a candidate again, and `results/IDEA_LEDGER.md` marks those `REVIVE?`.
The two failures that remain bugs to check for are a **stale-price artifact** and
a **control that scores as well as the treatment**.

## What the work is for

Find more, stronger and more independent sources of return, and get them to
paper (`docs/MISSION.md`). Breadth is the main lever: a modest signal across
many independent bets beats a good signal on a handful of correlated names. Say
which of these a piece of work does: adds a sleeve, widens a universe, improves
what is captured of a signal already held, or builds the path to paper.
