---
name: harness
description: How to run a backtest correctly in this repo — the canonical harness, the shift(2) convention, the lookahead asserts, the early/late time split and regimes, eras, the exposure report, the capacity table, and the reporting template. Use before writing any backtest or signal evaluation, and when a result needs to be comparable to existing numbers.
---

# The research harness

**Do not build another backtester.** The canonical one is
`scripts/research/harness.py`, shared by every family and the ML pipeline.
Extend it visibly, with a test.

Research is judged on **gross signal** (team lead, 2026-11-09, `docs/SYSTEM.md`
§5). This skill no longer carries a cost grid, turnover-matched net comparisons,
trial counters and their bars, or sealed-holdout steps: all were dropped for
research that day. `CLAUDE.md`, "Hard rules — research", is the authority.

```python
from scripts.research import harness
H = harness.cross_sectional_weights(signal, eligible, ...)   # or harness.event_weights(...)
res = harness.evaluate(H, R)       # applies H.shift(harness.EXEC_LAG): decide t, MOC fill t+1, earn t+2
rep = harness.report(H, R)         # full, fit / holdout (one early/late split), eras

# the CEF sleeve's own builders
from scripts.cef.band_frontier import build_targets, band, evaluate
from scripts.cef.spec import BAND_WIDTH     # never write a live parameter as a literal
```

| need | use |
|---|---|
| the gross headline and the eras | `harness.report(H, R)`: read the gross columns of `full` and `eras` |
| one early/late split | `report`'s `fit` and `holdout` rows split at `harness.HOLDOUT_START`. The names are from before the ruling; they are simply the early and late periods now. A different split point is stated with its reason |
| a family other than the CEF sleeve | `harness.cross_sectional_weights(...)` or `harness.event_weights(...)`, then `report` |
| prove a target builder reads no future | `harness.truncation_check(build, probes)` |
| an ML model | `scripts/research/ml.py`: `label_panel`, `walk_forward_splits`, `walk_forward_predict`; `cpcv_splits` for the overfitting distribution only; `reversal_gate` before trusting a complex model |
| a standard error under overlap or clustering | `newey_west_t`, `clustered_mean_diff` in `scripts/research/inference.py` |
| is variant A's Sharpe different from B's | `sharpe_diff` in `scripts/research/resampling.py` (block from `calibrate_block`) |

`harness.report` still returns net-of-cost columns and a `sign_flips` flag from
before the ruling. **Do not put them in a research table.** The harness has no
helper yet for regimes, exposures or the capacity table: compute them in the
idea's script from `res["pnl"]` and the weight panel, or add a tested helper to
the harness. Do not write a second scoring loop.

## The rules that stay

| # | rule |
|---|---|
| **H1** | Execution is **`shift(2)`** for anything traded at the close. Decide *t*, MOC fill *t+1*, earn *t+2*. Another fill (an open, an intraday window) is stated in a comment and asserted. |
| **H5** | **Eras** 2005–09, 2010–14, 2015–19, 2020–22, 2023–26 where the sample allows. |
| **H6** | **IC** = Spearman(signal *t*, forward return from *t+2*), non-overlapping, standard errors **clustered by date**. |
| **H7** | **No lookahead**, including in the data: NAV publication lags, filing acceptance times, index membership as of the day, first-release macro vintages. State the alignment in a comment; assert it at run time (`src/backtest/guard.py`). |
| **H12** | **One control.** Test where the mechanism cannot operate. A bug check, not a gate. |
| **H14** | **No decision rule keys on a number written in a document.** Re-measure. |
| **H15** | **Total returns.** If the distribution panel cannot cover a name-date, **raise**. |
| new | **One time split and two regimes** before paper. |
| new | **Exposures reported**, never a veto. |
| new | **Capacity shown** at $1M, $5M and $10M against ADV. |

## Why each convention exists

**`shift(2)`** — a signal that needs the fund's NAV cannot be computed until
after the close, so the decision is made in the evening and the earliest fill is
the *next* closing auction. `validate.py` once used `shift(1)`, entering at day
*t*'s close on day *t*'s NAV, and overstated the gross Sharpe materially
(`pre-clean-slate:results/cef/EXECUTION_CONVENTION_2026-09-10.md`).

**The time split** — an effect that exists only in one half of the sample is
usually a bug, a data change or a fluke. Reading both halves takes minutes.

**Regimes** — say which state variable defines them before looking (a credit
spread, a volatility index, the rate cycle), and build the label only from data
available on each date. An effect that lives in one regime is a finding with a
story, not a failure.

**Pre-2013 is thin on the CEF panel** — too few names clear the ADV filter, so
full-sample turnover is diluted and full-sample Sharpes are depressed. Report by
era (`CLAUDE.md` landmine 8).

**Exploring parameters** — allowed. Show the neighbours of the value you chose,
so the reader can see a plateau or a spike.

## Reporting template

```
                 ann ret    vol    gross SR   max DD   hit rate   turn/yr
---------------------------------------------------------------------------
full sample       x.x%     x.x%     x.xx      -x.x%     xx%        xx.x
early             ...
late              ...
regime A (named)  ...
regime B (named)  ...
control           ...
```

then:

```
exposures     beta equity   beta rates   beta credit   corr with each sleeve held
capacity      at $1M / $5M / $10M: largest position as % of ADV; share of positions above the stated participation
```

plus an era block where the sample allows, one equity-curve chart, the
reproducing command, and a line naming each panel and **its last date**. Every
figure labelled `[V]`/`[S]`/`[U]`. Capacity is a feasibility check, not a cost.

## Before you publish a number

- Is the panel current? *Stale is a form of wrong.*
- Is the price one that could be traded (an official close, not a mid or a
  stale NAV)?
- Does the control score as well as the treatment?
- Do the early and late halves agree?
- Has `quant-reviewer` read the script?
- Is the line in `results/IDEA_LEDGER.md`, in the same commit?
- Can someone reproduce it from the command you named? Run `/repro`.
