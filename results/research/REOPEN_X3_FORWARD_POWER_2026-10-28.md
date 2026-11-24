# Re-open (3): X3 hedged against TERM — the forward power check, 2026-10-28

**Zero trials. No returns computed.** Reproducer: `python3 -m scripts.research.reopen_x3.forward_power`
(`scripts/research/reopen_x3/forward_power.py`). It reads only the registry's XASSET bar inputs.

## Why a forward record is the only evidence left

X3 (XASSET-2) is the month-end Treasury extension: long IEF over the last three sessions of each month.

- **It is the slate's one real effect** (`results/xasset/XASSET_RESULTS_2026-10-14.md` [S]): gross Sharpe
  1.04, Newey–West t 4.94, alpha 5.33%/yr (t 4.54).
- **It failed D4 on TERM:** β 0.34, CI 0.29–0.39. It is also D2 at 15bp, before any hedge leg is added.
- **Under T+1 settlement** (from 2024-05-28) its Sharpe is 0.44.
- **Both its fit and its holdout have been seen**, so a TERM-hedged variant scored on that history is post hoc.

## The chance that a forward record passes

The gate is the team lead's safeguarded paper bar (`docs/SYSTEM.md` §5, 2026-10-28), applied as a fifth
declared XASSET test. ρ̄ and V come from the registry's four stored series. Normal returns are assumed.
Every figure is [V] from the reproducer.

| true annualised Sharpe of the hedged sleeve | 1 y | 2 y | 3 y | 5 y | 10 y | 80% power at 5% |
|---|---|---|---|---|---|---|
| 0.44 (X3 under T+1) | 0.01 | 0.02 | 0.02 | 0.04 | 0.07 | 40.5 y |
| 0.55 (X3 net at 5bp, unhedged) | 0.01 | 0.03 | 0.04 | 0.07 | 0.13 | 25.9 y |
| 1.0 (X3 gross, no hedge cost) | 0.04 | 0.09 | 0.16 | 0.31 | 0.61 | 7.8 y |

## Reading

- **UNDERPOWERED: no trial.** At every plausible net Sharpe, the chance that a forward record passes is
  far below the research-idea power gate's 0.5. Even at the gross Sharpe before hedge costs, it takes
  about ten years to beat a coin toss.
- **The hedge leg adds turnover to a sleeve that already fails at 15bp.**
- **What would reopen it:**
  - a cheaper expression with lower turnover;
  - or a forward shadow record kept for information only, which spends nothing and decides nothing.
