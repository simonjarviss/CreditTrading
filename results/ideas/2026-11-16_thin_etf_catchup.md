# Idea card — Thin ETFs catching up to their factor hedge: real on the day we cannot trade, gone by our fill

**Slug:** `thin_etf_catchup` · **Written:** 2026-11-16, **interrupted that day** (the editor
was force quit after `explore.py` had run once and before `checks.py` had run or this card
existed); **completed 2026-11-18** by a second researcher from the files on disk ·
**Status:** KILLED as a trade under the desk's fill rule. The fixed book is 0.18 gross
(t 0.92); one session later it is −0.03; no bucket, class or leg earns a tenth of its own
quoted spread per unit traded ·
**Reproducer:** `QUANTT_ENV_FILE=<env> python3 results/ideas/thin_etf_catchup/stage.py`, then
`python3 results/ideas/thin_etf_catchup/explore.py` and `checks.py` (aggregates in
`results.json` beside them) ·
**Panel:** every CRSP ETF (security type FUND, subtype ETF) from `crsp_a_stock.dsf_v2` on R2,
9,221,182 fund-days, 6,933 funds, 2000-01-03 to **2025-12-31**, dead funds included (2,099
have no return in the last month of the panel). 95.4% of rows traded; 99.97% carry a closing
bid and ask. Licensed rows are under `~/quantt_research/thin_etf_catchup/`, not in the
repository. No Yahoo data was used. All figures below are [V], computed 2026-11-18.

## The idea

A thin ETF's last trade can be hours old at the bell, so its close-to-close return lags the
market and catches up the next day. The desk decides at t's close and fills at t+1's close,
so the catch-up day is not ours. The question: is any drift left from t+1's close, in which
funds, and is it larger than the spread? The graveyard holds the neighbour (`single-fund-PD`:
the ETF leads a stale NAV) but nothing on ETF price against liquid ETF prices under shift(2).

## What was fixed before the test (2026-11-16, kept word for word in `explore.py`)

Only counts had been read (funds a year, share of zero-volume rows, factor start dates).

- **Hedge:** SPY, IWM, QQQ, EFA, EEM, TLT, HYG, GLD from the same panel; betas by OLS on the
  250 sessions strictly before each 21-session block (asserted in code).
- **Signal:** the fund's return less beta × factors, summed over five sessions (S5); S1 is
  one session.
- **Class:** by rule from the best-fitting factor (US equity, international, bond,
  commodity, low fit); geared and inverse funds are out.
- **Buckets** on 21-session mean dollar volume: THIN $25,000–$1M (A below $250,000, B
  above), MID $1M–$10M, LARGE $10M–$100M, LIQUID over $100M (the control). Price ≥ $5.
- **Book:** long the fifth that most lagged its hedge, short the fifth that most led, equal
  weights, each fund hedged with the factor funds; decided at t, filled at t+1's close.
- **Main:** THIN, S5, hold 5. The other five cells of {S1, S5} × {1, 5, 20} are shown.
- **Controls:** LIQUID; THIN with the signal 20 sessions old.
- **Artifact tests named in advance:** one-session skip; signal and returns rebuilt on
  closing mid quotes; buy-and-hold per event against the quoted spread.
- **Expected:** nothing left after the fill; LIQUID zero.
- **Declared not done:** the international-holiday case (no home-market calendar in the panel).

## What it showed (gross, shift(2), no costs) [V]

2001-01-08 to 2025-12-31. MAIN holds about 203 funds a day; median dollar volume $216,753,
median price $28.6, median quoted spread 28bp; ETF legs turn 78 times a year (105 with the
hedge legs). 97.1% of THIN fund-days traded on day t.

| | Sharpe (t) | return / vol | halves | 2002–08 | 2009–15 | 2016–19 | 2020–22 | 2023–25 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **MAIN: THIN, S5, hold 5** | 0.18 (0.92) | 0.58% / 3.15% | 0.22 / 0.13 | 0.28 | −0.21 | −0.14 | 0.23 | 0.58 |
| MAIN on closing mids | 0.17 (0.84) | 0.47% / 2.80% | 0.18 / 0.16 | 0.09 | 0.00 | −0.04 | 0.27 | 0.58 |
| MAIN filled one session later | −0.03 (−0.16) | −0.10% / 3.11% | −0.05 / 0.00 | −0.04 | −0.43 | −0.02 | −0.02 | 0.42 |
| mids and one session later | −0.08 (−0.40) | −0.22% / 2.76% | | | | | | |
| control: LIQUID, S5, hold 5 | 0.10 (0.41) | 0.48% / 5.04% | 0.10 / 0.09 | −0.16 | 0.18 | −0.05 | −0.04 | 0.51 |
| control: signal 20 sessions old | 0.05 (0.26) | 0.14% / 2.79% | 0.03 / 0.11 | 0.13 | −0.25 | 1.02 | 0.32 | −0.85 |

Legs of MAIN, each hedged: long 0.21 (t 1.03), short −0.03 (t −0.16). Worst drawdown −15.7%.

The grid in THIN, none picked:

| | hold 1 | hold 5 | hold 20 |
|---|---:|---:|---:|
| S1 | 0.36 (1.77) | 0.59 (2.96) | 0.06 (0.29) |
| S5 | 0.57 (2.85) | **0.18 (0.92)** | −0.10 (−0.50) |

Splits named in advance (S5, hold 5):

| | Sharpe (t) | funds a day | median dollar volume | median spread |
|---|---:|---:|---:|---:|
| THIN-A | 0.02 (0.07) | 134 | $98,755 | 33bp |
| THIN-B | 0.21 (1.05) | 100 | $495,695 | 23bp |
| MID | 0.47 (2.37) | 140 | $2,783,008 | 12bp |
| LARGE | 0.17 (0.80) | 72 | $23,233,246 | 5bp |
| LIQUID (control) | 0.10 (0.41) | 32 | $251,705,547 | 3bp |
| THIN US equity | 0.17 (0.86) | 102 | $231,156 | 23bp |
| THIN international | 0.08 (0.40) | 70 | $198,992 | 37bp |
| THIN bond | 0.16 (0.65) | 39 | $254,194 | 21bp |
| THIN commodity | 0.01 (0.05) | 6 | $244,245 | 30bp |
| THIN low fit | −0.26 (−1.08) | 11 | $144,656 | 48bp |
| THIN, traded on t | 0.19 (0.95) | 197 | $224,200 | 28bp |
| THIN, no trade on t | 0.18 (0.75) | 12 | $56,340 | 52bp |

Buy-and-hold per event (THIN, S5, t+1 close to t+6 close, no rebalancing, 635,873 events a
side): long less short **+3.1bp per five sessions (t 0.92)** on trade prices, +2.2bp
(t 0.72) on mids, against a 28bp median spread. Mean hedged long −0.2bp, short −2.0bp.

The expectation held: nothing on the main cell, nothing on the control.

## Checks that were not pre-specified (`checks.py`, written 2026-11-16 after the one run, first run 2026-11-18) [V]

Written to show where the catch-up goes, not to rescue it.

**Event time.** Bottom fifth less top fifth on yesterday's gap (S1), mean gap in bp (t):

| bucket | prices | t+1 (not ours) | t+2 (first day earned) | t+3..t+6 | spread |
|---|---|---:|---:|---:|---:|
| THIN-A | trades | +39.6 (42.8) | −0.2 (−0.4) | +2.4 (2.2) | 34bp |
| THIN-A | mids | +11.3 (16.5) | +0.1 (0.1) | +1.6 (1.4) | 33bp |
| THIN-B | trades | +22.2 (32.1) | +1.5 (2.4) | +2.7 (2.5) | 23bp |
| THIN-B | mids | +6.1 (10.0) | +0.7 (1.3) | +2.7 (2.5) | 23bp |
| MID | trades | +10.7 (16.9) | +1.5 (2.4) | +3.7 (3.3) | 13bp |
| MID | mids | +2.8 (4.5) | +0.8 (1.3) | +4.2 (3.6) | 12bp |
| LARGE | trades | +5.5 (7.5) | +0.9 (1.3) | +3.3 (2.6) | 5bp |
| LIQUID | trades | +9.2 (7.8) | +0.0 (0.0) | +6.2 (2.9) | 3bp |

**The lane's literal question.** Slope of a fund's gap on its factor-implied return of day
t, day-clustered: on t+1, 0.087 (t 14.8) in THIN-A, 0.054 in THIN-B, 0.033 in MID, 0.020 in
LARGE, 0.005 (t 1.2) in LIQUID on trade prices; on mids 0.025, 0.022, 0.024, 0.018, 0.004.
On **t+2 every dollar-volume bucket is within ±0.006** (largest t 2.1, MID on mids). By class
on t+1, on mids: bond 0.055, commodity 0.039, international 0.034, US equity 0.016. On t+2:
commodity 0.027 (t 2.2, six funds a day), nothing else above t 1.6.

**Per unit traded.** The cells with t above 2 earn 1.1 to 2.0bp gross per unit of ETF
turnover (THIN S1 hold 5: 1.24bp; THIN S5 hold 1: 1.13bp; MID S5 hold 5: 1.96bp) against a
half spread of 14.5bp, 14.0bp and 6.1bp.

- **The catch-up is real and is not ours.** About 9% of the factors' move reaches a
  $100,000-a-day fund's close a day late; a long-short on it shows 40bp on t+1.
- **Two thirds of it is the last trade, not the quote.** On closing mids the t+1 figure
  falls from 39.6bp to 11.3bp, which is a third of that bucket's spread. Even with a fill at
  t's close it could not have been dealt.
- **By t+2 it is over.** Zero in THIN-A; 1.5bp a day at most elsewhere.
- **A small slow reversal exists everywhere, LIQUID included** (2 to 6bp over t+3..t+6).
  It is ordinary residual reversal, not staleness, and is a fraction of the spread in every
  bucket except LIQUID, where it is t 2.9 before any multiple-comparison allowance and the
  book built on it is 0.10.
- **Zero-volume days do not matter here.** Only 2.9% of THIN fund-days had no trade, and
  CRSP's price on such a day is already the quote midpoint [S: CRSP convention, not re-read].

## Fixes and changes after the interruption

None to the rule, universe, signal, windows, weights, hedge or controls. `explore.py` was
re-run unchanged on 2026-11-18 and `results.json` matched the 2026-11-16 file key for key.
`checks.py` was run as written. The staged panel was verified (opens, row count, last date
2025-12-31) and reused.

## What I conclude

1. Killed as a trade. The effect the lane describes is large on t+1 and absent from the
   desk's first earning day; MAIN is 0.18 and turns negative with one more session's delay.
2. No sub-group survives. The best split (MID, 0.47, t 2.37, 0.71 / 0.15 by halves) is one
   of twelve, earns 2bp per unit traded against a 6bp half spread, and its control group
   LARGE shows the same sign.
3. The grid's two cells near t 3 (S1 hold 5, S5 hold 1) are faster versions of the same
   1bp-per-trade reversal at 14bp half spread, and are strongest in 2002–08.
4. The short leg, the one a thin fund's borrow would make hard anyway, contributes nothing.

## What I could not do

- The international-holiday case: no home-market calendar or fund-to-country map in the
  panel; not attempted. The international class as a whole shows 0.08.
- A per-fund sector hedge: QQQ stands in. Residual sector moves are noise in the gap, not
  bias, but they lower power.
- Asset class is returns-based, not from the prospectus; munis and short bonds sit in "low
  fit".
- 4,645 of 2,267,105 held fund-days in MAIN (0.2%) have no CRSP return and score zero.
- Borrow availability for thin ETFs was not measured.

## What would reopen it

- A venue or order type that fills at t's close on the quote (not this desk's rule), and
  even then only for the 6 to 11bp left on mids against a 23 to 33bp spread.
- Intraday NAV or last-trade timestamps, to select funds whose close is known to be stale
  and whose quote has not yet moved; daily CRSP cannot show that.

**Not independently reviewed.**
