# NAV hedge on the core book: screened and CLOSED at the power gate (2026-11-02)

**Ruling (team lead, 2026-11-02):** close the Sharpe-framed NAV hedge as
**UNDERPOWERED** at Stage 0.
- Zero trials, no hedged return computed, no data pulled.
- If it is ever run, it spends the **CEF** counter.
- In its place, build a **report-only exposure readout** of the live book to
  MUNI / TERM / credit / loans (zero trials; see the last section).

The ledger edit for `docs/RESEARCH_STATE.md` was sent to the session that owns
that file.

## Why it was looked at

The live attribution (`results/cef/LIVE_ATTRIBUTION_2026-11-02.md`, PR #26)
split the paper book's −$982.14 over 2026-09-29..10-30 into:

| component | USD |
|---|---:|
| discount part (the signal's leg) | +1,583.47 |
| NAV part | −2,250.74 |
| of which the muni group (short MQY/MHD) | −1,849.36 |
| fill | −308.71 |
| fees | −6.16 |

The question: could an ETF overlay remove the NAV exposure while keeping every
CEF weight?

**This window inspired the idea, so it must never be used to choose an
instrument or a hedge ratio.**

## Screen

| check | finding |
|---|---|
| Graveyard | No KILLED or CLOSED entry is a linear ETF overlay on the core book. Its nearest relatives died of something it shares: hard muni neutrality (GN-N1) ran the vol scalar to its cap and gross past the ceiling [S]. The withdrawn ex-date MUB/IEF amendment took gross from 1.76 to 2.44, and the cap bound on 41.6% of rows [S]. |
| Mechanism | H0: the book's ETF-spanned NAV exposure is unpriced once the signal has chosen positions, so hedging raises the Sharpe by SR_B(1/√(1−R²)−1). The prior leans H0: reversion runs through price, not NAV [S SCR-MACRO-DAYS]. |
| Power | The factor R² on record is 0.011–0.074 [S PORTFOLIO_FRAMEWORK_2026-10-15 §6.4]. Even with an oracle hedge (true betas, no estimation noise), at book Sharpe 0.96 over 9.5 years: P(paired ΔSR passes one-sided 5%) is **0.07–0.11**, and P(PRESENT at N=54) is at most **0.002**. P(pass) = 0.5 needs the hedge to remove **R² ≥ 0.51** (one-sided) or **0.79** (Šidák, N=54). [V arithmetic on cited inputs: `results/cef/navhedge_2026-11-02/navhedge_power.py`, which reads no data; it re-ran on this branch 2026-11-02.] |
| Return on capital | Under the 2026-10-29 sizing rule the margin term binds [S], and Reg T does not net an ETF against a CEF. So hedge gross lowers the derived multiplier, and it cannot raise % return on capital. It could only lower vol at the same multiplier. |
| Counter | **CEF**, not MACRO. The statistic is dominated by the CEF book's own returns, selected over 52 CEF trials. At MACRO N=1 the desk bar is 0, and the unhedged book alone would pass DSR with P ≈ 0.90 [U arithmetic], which is a multiplicity leak. |
| Timing | Trial 53's H-VT and its stops were derived on the unhedged raised book. A hedge during its 120 armed sessions would confound that read. |

## Plumbing found on the way (market-structure seat, read-only)

These matter to anyone who reopens the idea.

- **The runner refuses a hedge leg as built.**
  - Gate 9 refuses the session if the account holds any symbol outside the
    universe.
  - `decide` raises on a target outside `frozen.universe`.
  - Gate 5 needs a NAV for every universe name.
  - Verify raises `UnmappedExchange` for ARCA- and BATS-listed names (MUB,
    HYG, BKLN, SRLN; HYD).
  - `dist_score` marks any symbol without distribution-panel rows as
    UNMEASURED.
- **Borrow.** The muni ETFs were read not shortable at Alpaca on 2026-10-15
  and 10-18 (MUB, VTEB, TFI, HYD, SUB, MLN, SHM) [V on those dates; borrow
  changes daily]. So the hedge is one-sided whenever the book is long munis.
- **Data.** There is no muni ETF before 2007-09-11 and no loan ETF before
  2011-03-04. MUB and BKLN are not in `data/etf_daily.parquet`. The rv
  panels end 2026-10-09 [V, read-only].
- **NYSE Arca's closing freeze is 15:59.** That is now recorded as a dated
  correction in `docs/REFERENCES.md` §3 and `docs/BRIEF.md` (SEC Rel.
  34-103886).

## What would reopen it

A measured, run-time R² of the book on a candidate ETF set (H14: not the
figure above) at or above the run-time R²*. The Power station would
re-measure it with `scripts/cef/portfolio_baseline.py`. If it clears, the
choice is between a pre-registered Sharpe test and a voltarget-style
risk-only trial. **That choice is the team lead's.** Futures or portfolio
margin would remove the Reg T objection and are also reasons to look again.

## Successor: the exposure readout (report only, zero trials)

This is the deleted `/api/factors`, rebuilt as position-based daily
telemetry: the live book's exposure to MUNI, TERM, credit and loans, so the
next muni-vs-taxable move is measured, not inferred from 24 sessions.

The rule is declared before the first reading:
- A breach goes to the team lead's review.
- **No hedge is ever added automatically.**

It reads the book; it never trades. It is to be specified and built as the
next phase and reviewed before it runs.
