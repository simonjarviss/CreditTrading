# Harness restructure: evaluate() moves to scripts/research/harness.py (2026-10-27)

Zero trials. No counter moved. No spec key touched.

**Ruling.** On 2026-10-27 the team lead said evaluate() may be "restructured as
necessary". The two named gaps were no shared harness for non-CEF ideas and no
ML pipeline. This note proves the restructure changes no number.

## What moved

- `scripts/research/harness.py` is now the one accounting path:
  - `EXEC_LAG = 2` is a constant. No function takes a lag.
  - `held`, `evaluate`, `label`, `cost_grid` and `report` (headline, cost grid, H5 eras, H13 fit and holdout rows).
  - `cross_sectional_weights` and `event_weights` are target builders for the non-CEF families.
  - `truncation_check` is the structural lookahead guard.
- `scripts/cef/band_frontier.evaluate` delegates with `nan_policy="legacy"`. That is the old body verbatim, so every existing caller is unchanged. E1 depends on it: `hold_gaps` checks its CRSP gaps first, and only then does it rely on the NaN skip. New code uses the default, `"raise"`.
- `HOLDOUT_START` now has one copy, in the harness.

## No-op proof [V, 2026-10-27]

- **Method.** `hash_eval.py` hashes every evaluate() output key (values plus index bytes) for three policies: the live band, calendar(2) and band 0.016. Each policy is run on price and on total returns, which gives 42 hashes.
- **Data.** The live CEF panels, with targets ending 2026-10-14 (5,480 rows).
- **Comparison.** One run on a detached checkout of af0cb35 (before), one on this branch (after). The two sets of hashes are **identical**. They were re-run after the legacy-policy fix, and are identical again.
- **Tests.** `scripts/research/tests/test_harness.py`. Each guard was checked to fail against the old behaviour: EXEC_LAG=1, the old NaN-skipping body, and `R.shift(-1)` as the label.

## Found, not changed

- **Zero-filled returns.** `build_targets()` zero-fills its return panel. On the live band, 32 of 35,776 held name-days have a NaN raw return that this books as 0.0 [V, same run]. Changing it would move the live baseline, so that is a separate decision.
- **A second engine.** `src/backtest/engine.py` (the Phase-2 ETF engine) applies weights from t+1's return, which is shift(1). Nothing on the research path calls it. Don't route new families through it.
