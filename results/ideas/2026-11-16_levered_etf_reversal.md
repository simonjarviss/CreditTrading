# Idea card — Fading the closing footprint of leveraged ETFs: real for one session, gone before the desk can fill

**Slug:** `levered_etf_reversal` · **Written:** 2026-11-16 ·
**Status:** SET ASIDE. Under the desk's fill (decide at t, fill at t+1's close) the fixed
book is 0.09 gross (t 0.37) on sector and index underlyings and −0.32 (t −0.63) on single
stocks, and both controls score higher. The give-back does exist, in the sector group
only, but all of it happens between t's close and t+1's close: +11.3bp an event (t 5.6),
rising with the flow share, on mid quotes too, and shrinking every era ·
**Reproducer:** `QUANTT_ENV_FILE=<env> python3 results/ideas/levered_etf_reversal/stage.py`,
then `mapping.py`, `explore.py` and `checks.py` in the same directory ·
**Panels:** CRSP daily rows on R2 for every security of subtype ETF (6,924, dead funds
included) from 2006-01-03, and for common stocks ever in the largest 1,000, to
**2025-12-31**. Licensed rows are under `~/quantt_research/levered_etf_reversal/`, not in
the repository. No Yahoo data was used.

## The idea

A daily leveraged or inverse fund with multiple b must trade b(b−1) × assets × the day's
return in its underlying near the close, in the direction of the move. If that is large
against the underlying's volume, the close is pushed too far and should come back. The
desk fills at the next close, so only a give-back that continues after t+1's close is
tradable here.

## What was fixed before any forward return was read

Read first: the same-day fit of each fund on its underlying, event counts, and the
distribution of the flow share by year.

- **Funds, by rule** (`mapping.py`): CRSP's name file carries the trust, not the fund, so
  a fund is identified by what it does: best-fitting candidate underlying with R² ≥ 0.90,
  yearly slope within 12% of a multiple. 174 sector and index funds (−3, −2, −1, 2, 3
  only) on 45 underlying ETFs from a fixed list of 54 excluding SPY, QQQ and DIA; 199
  single-stock funds on 96 stocks. [V]
- **Flow share S:** Σ b(b−1) × fund shares × price, all at t−1, × |return at t| ÷ the
  underlying's dollar volume at t.
- **Event:** S ≥ 10% (sector and index) or S ≥ 1% (single stocks), about the pooled 90th
  percentile of each group; underlying trades $20M a day and costs $5.
- **Trade:** fade the move, 10% of the book per event, held two sessions (t+2 and t+3),
  SPY against it, gross capped at 100%.
- **Controls:** A, days with a move in the underlying's own top decile and S under a
  quarter of the event level (including days before any fund existed); B, such days with
  no fund at all (single stocks: 1,380 large stocks that never had one).
- **Expected:** positive over t+2..t+3, above A and B, larger with larger S and in years
  with more leveraged assets.

## What it showed (gross, shift(2), no costs) [V]

Book, hedged with SPY (`harness.evaluate`):

| | Sharpe (t) | return / volatility | halves | 2007–08 | 2009–15 | 2016–19 | 2020–22 | 2023–25 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Sector and index, events** (2007–2025) | 0.09 (0.37) | 0.7% / 7.7% | 0.08 / 0.09 | 0.27 | −0.05 | −0.05 | 0.45 | 0.06 |
| control A, big move, little or no flow | 0.29 (1.28) | 2.1% / 7.3% | | | | | | |
| control B, big move, no fund alive | 0.37 (1.60) | 2.4% / 6.6% | | | | | | |
| events less A / less B | −0.16 (−0.71) / −0.20 (−0.88) | | | | | | | |
| **Single stocks, events** (first event 2024) | −0.32 (−0.63) | −5.2% / 16.6% | none / −0.45 | | | | | −0.36 |
| control A, same stocks, little or no flow | 0.40 (0.79) | 9.9% / 25.0% | | | | | | |
| control B, stocks with no fund | 0.03 (0.06) | 0.3% / 10.8% | | | | | | |

Per event, buy and hold, signed as a fade, less SPY (t on the daily mean across events):

| window | sector events (14,660) | sector control A (14,180) | single-stock events (1,720) | single control B (115,678) |
|---|---:|---:|---:|---:|
| t+1, **not tradable here** | **+11.3bp (t 5.56)** | +0.2bp (0.46) | −3.3bp (0.57) | −2.3bp (1.06) |
| t+2..t+3, the trade | +0.9bp (0.52) | +3.2bp (0.93) | −28.0bp (−0.54) | −1.3bp (0.61) |
| t+3..t+4 | −1.4bp (−0.71) | +5.4bp (1.59) | +6.0bp (0.60) | +3.1bp (2.14) |
| t+4..t+6 | +2.6bp (0.24) | +9.3bp (1.96) | +9.8bp (1.41) | +7.1bp (1.10) |

Dose, sector group, big-move days with a fund alive:

| flow share | events | t+1 | t+2..t+3 |
|---|---:|---:|---:|
| under 2.5% | 6,759 | −0.5bp (t −0.18) | −1.8bp (−0.24) |
| 2.5% to 10% | 4,181 | +3.7bp (0.91) | +9.4bp (2.33) |
| 10% to 25% | 1,968 | +10.2bp (1.18) | −6.6bp (−0.75) |
| 25% and over | 1,124 | +29.3bp (4.06) | +1.9bp (0.01) |

**What is held.** Sector events: 32 underlyings, median dollar volume $402M a day, price
$69, median move 1.8%, closing spread median 3.5bp (90th percentile 7.8bp), turnover 186
times a year. Single-stock events: 32 stocks, $2.2bn a day, price $136, median move 4.8%,
spread 3.4bp, turnover 85. Capacity is not the constraint. [V]

**By year, the tradable window** is within ±14bp an event every year for the sector group
(best 2007 +19bp on 56 events, 2022 +9bp, t 1.6) with no trend as leveraged assets rose
from $6bn (2008) to $33bn (2025). Single stocks: 2024 −29bp, 2025 −28bp. [V]

## Checks that were not pre-specified (`checks.py`, sector group, the t+1 window) [V]

| | |
|---|---|
| t+1 by era, events | +33.6bp (t 2.5) 2007–08, +17.4 (3.4) 2009–15, +11.1 (2.4) 2016–19, +8.1 (2.1) 2020–22, **+4.8 (2.1) 2023–25** |
| t+1 by era, control A | +5.8, +3.5, −1.3, −4.9, −1.9; no era above t 1.3 |
| t+1 on closing mid quotes (no bounce) | +11.2bp (t 5.45); S ≥ 25%: +14.6bp (5.56); control A −0.7bp |
| by underlying (21 with 100+ events) | 76% positive; without the three busiest +10.7bp (t 4.38) |
| the same book filled at t's own close, one session | 1.53 (t 6.67), 8.8% / 5.7%; halves 1.70 / 1.38; 2023–25 1.09 |

The last row is **not a result the desk can have**: the flow is only known at the close
it would need to trade in. It is there to size what is left behind.

- **The mechanism is visible, for one session.** The next-day give-back is absent on
  equally large moves without forced flow, rises with the flow share, is the same on mid
  quotes and is not a few names.
- **Nothing is left after t+1's close.** The tradable window is 0.9bp against a 3.5bp
  spread, and the controls do better.
- **It is being competed away.** The one-session give-back has fallen from 34bp to 5bp
  an event while leveraged assets rose fivefold; the opposite of what was expected, and
  5bp is about one spread.
- **Single stocks show nothing in any window.** Flow shares are small (median event 1.8%
  of volume; 123 stock-days at 5% or more, 91 in one stock) and the sample is 2024–25 only.

## What I conclude

1. Dead under the desk's fill convention, in both groups. Not a shadow candidate.
2. Leveraged-fund rebalancing does move sector ETF closes and the move comes back by the
   next close. That is a measured fact worth keeping, not a trade here.

## Limits [U]

- The sector flow share divides by the ETF's own volume, not its constituents'; it ranks
  days and overstates the level by an unknown factor per underlying.
- CRSP's share counts for most NYSE Arca funds change monthly, so fund assets can be up
  to a month stale in shares; Nasdaq-listed funds update daily.
- The candidate sector ETFs are a list of funds alive at 2025-12-31 (the leveraged funds
  themselves include dead ones). Single-stock underlyings are common stocks only, so
  funds on ADRs are missed. No clean "no leveraged fund" control exists for sectors.
- The t+1 window was not split into overnight and intraday; the staged panel has no opens.

## What would reopen it

- A ruling that a book may decide before the close on the day's move so far (the flow is
  nearly known by 15:50) and fill in that same close. That is an intraday decision and
  needs intraday bars to test; the 2023–25 size (5bp, Sharpe 1.09 before a 3.5bp spread)
  says it would have to be checked net of the spread first.
- Single stocks, once a few years exist with flow shares above 5% in more than one name.

**Not independently reviewed.**
