# Idea card — A soft cap on one fund group's net weight in the core CEF book

**Slug:** `core_group_cap` · **Written:** 2026-11-16 ·
**Status:** SET ASIDE. No cap tested does more than a plain cut in size would. The flat 25%
cap keeps the Sharpe (1.13 against 1.15) only because it shrinks the book by a fifth; an
uncapped book shrunk by the same fifth has the same Sharpe and a smaller worst window. Caps
derived from each group's own pre-2020 history are zero for the muni group and cost up to
0.35 of Sharpe. Recommendation: do not add a group cap ·
**Reproducer:** `python3 results/ideas/core_group_cap/explore.py --data <data/cef>`, then
`python3 results/ideas/core_group_cap/checks.py --data <data/cef>` ·
**Panels:** the desk's CEF price and NAV panels, read-only, last NAV row **2026-10-14**
(prices 2026-10-15). Spec `cef_discount.v9.20261102`, read through `scripts/cef/spec.py`.
Nothing in `ops/specs`, the sleeve or `data/` was touched.

## The idea

The paper book lost about 3.2% of capital in 34 sessions on the NAV moves of two muni funds
it was short through a muni rally (`results/ideas/2026-11-15_core_nav_hedge.md`). An ETF
hedge did not help. Hard group neutrality was killed long ago (0.97 → 0.82,
`docs/RESEARCH_STATE.md`). The unread middle: let the signal take a group view, but limit
its size.

## What was fixed before any capped return was read (`explore.py` docstring)

- **Book:** `build_targets()` then `band(T, BAND_WIDTH)`, unchanged; shift(2) through
  `harness.evaluate`. 13 funds: 8 multi-sector, 2 muni, 2 high yield, 1 loan. Scored from
  the first session the book holds, 2013-06-25, to 2026-10-14. Weights are before the 1.3×
  sizing; the 34-session windows are at 1.3×, as in the earlier card.
- **Caps on each group's absolute net target, applied before the band:** MED (the group's
  pre-2020 median), P75 (its pre-2020 75th percentile), F25 (25% for every group), and XP75
  (P75 on an expanding window ending the session before, so no lookahead).
- **Three constructions:** PRORATA (scale the breaching group's positions to the cap; gross
  falls and the book carries the net that was cut), REGROSS (PRORATA, then the whole book
  scaled back to its old gross), NEUTRAL (clip the group nets, rebalance the two sides so
  they still sum to zero, move each group's funds by an equal amount; with a cap of zero
  this is hard neutrality).
- **Controls:** the uncapped book cut to the capped book's mean gross; 200 random
  relabellings of the 13 funds into groups of the same sizes; the live policy's gross
  ceiling in place of the plain band.
- **Expected:** a cap costs 0.02 to 0.08 of Sharpe and cuts the NAV part's worst 34
  sessions by more than the size cut alone.

## What the group nets look like [V]

| absolute net target | pre-2020 median | pre-2020 p75 | from 2020 median | from 2020 p95 | max |
|---|---:|---:|---:|---:|---:|
| muni (2 funds) | 0.00 | 0.00 | 0.00 | 0.48 | 0.66 |
| multi-sector (8) | 0.20 | 0.39 | 0.34 | 0.70 | 0.97 |
| high yield (2) | 0.29 | 0.44 | 0.16 | 0.49 | 0.77 |
| loan (1) | 0.00 | 0.00 | 0.05 | 0.49 | 0.69 |

**The muni funds have no target at all before 2020.** So the caps the brief asked to be
derived from the group's own pre-2020 history are zero for the muni group (and for the loan
fund): MED, P75 and XP75 remove those groups, they do not soften them. Only F25 is a soft
cap on the muni group. It binds on 54% of sessions for multi-sector, 38% for high yield,
19% for loan and **6% for muni**.

## What it showed (gross, shift(2), no costs) [V]

Worst windows are 34 sessions, % of capital at 1.3×. Eras are Sharpe ratios.

| | Sharpe (t) | return / vol | worst drawdown | worst 34: NAV part | worst 34: book | turnover a year | mean gross | halves | 2013–15 | 2016–19 | 2020–22 | 2023–26 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| uncapped | 1.15 (4.20) | 7.60 / 6.60 | −14.4 | −3.52 | −7.75 | 22.5 | 1.33 | 0.87 / 1.45 | 1.28 | 0.56 | 1.01 | 1.79 |
| F25 PRORATA | 1.13 (4.11) | 6.04 / 5.35 | −10.8 | −3.00 | −8.19 | 15.4 | 1.05 | 0.96 / 1.32 | 1.25 | 0.72 | 0.88 | 1.67 |
| F25 REGROSS | 1.16 (4.23) | 7.60 / 6.54 | −15.8 | −2.94 | −8.55 | 22.5 | 1.32 | 0.87 / 1.47 | 1.28 | 0.59 | 1.05 | 1.73 |
| F25 NEUTRAL | 1.19 (4.33) | 6.81 / 5.73 | −11.2 | −2.97 | −8.18 | 18.3 | 1.15 | 1.04 / 1.35 | 1.40 | 0.74 | 0.96 | 1.69 |
| P75 PRORATA | 0.89 (3.24) | 5.33 / 5.99 | −15.3 | −5.37 | −8.91 | 16.9 | 1.06 | 0.73 / 1.05 | 1.17 | 0.38 | 0.87 | 1.19 |
| P75 NEUTRAL | 1.05 (3.82) | 5.90 / 5.63 | −14.4 | −3.13 | −8.71 | 17.8 | 1.07 | 0.82 / 1.33 | 1.28 | 0.48 | 0.95 | 1.64 |
| XP75 PRORATA | 0.94 (3.43) | 5.67 / 6.02 | −13.1 | −4.63 | −8.47 | 17.0 | 1.10 | 0.84 / 1.05 | 1.24 | 0.50 | 0.78 | 1.27 |
| XP75 NEUTRAL | 1.06 (3.85) | 5.95 / 5.63 | −12.9 | −3.36 | −8.63 | 18.0 | 1.11 | 0.84 / 1.34 | 1.27 | 0.51 | 0.97 | 1.60 |
| MED PRORATA | 0.80 (2.92) | 3.93 / 4.91 | −13.3 | −2.65 | −8.70 | 13.2 | 0.89 | 0.68 / 0.95 | 1.08 | 0.35 | 0.75 | 1.13 |
| MED NEUTRAL | 1.13 (4.12) | 6.08 / 5.38 | −11.9 | −2.81 | −8.71 | 16.3 | 1.01 | 0.95 / 1.35 | 1.37 | 0.63 | 0.95 | 1.67 |
| hard neutral (cap 0) | 1.11 (4.05) | 5.55 / 4.99 | −10.6 | −2.61 | −8.80 | 14.8 | 0.94 | 1.04 / 1.19 | 1.44 | 0.70 | 0.89 | 1.50 |

The P75, XP75 and MED REGROSS rows are worse than their PRORATA rows (Sharpe 0.80 to 0.89,
drawdowns near −20%) and are in `results.json`.

**The NAV and discount parts** (return a year / volatility, %):

| | NAV part | discount part |
|---|---:|---:|
| uncapped | −0.28 / 2.56 | 7.88 |
| F25 PRORATA | +0.04 / 2.03 | 5.99 |
| F25 NEUTRAL | −0.22 / 2.09 | 7.03 |
| P75 PRORATA | −1.06 / 2.24 | 6.39 |

- **The return falls with every cap.** F25 PRORATA earns 1.57 points a year less than the
  uncapped book (t −2.35 on the daily difference); F25 NEUTRAL 0.79 less (t −1.43); the
  derived caps 1.5 to 3.7 less (t −1.8 to −4.0).
- **F25's Sharpe is unchanged because it is a smaller book,** not a better one: gross falls
  21% (PRORATA) or 13% (NEUTRAL) and volatility with it. Put back to the old gross
  (REGROSS), the caps are exceeded by 1.6 times on average and the book is the uncapped
  book again (1.16, same return).
- **The whole book's worst 34 sessions get worse under every cap** (−8.2 to −8.9 against
  −7.75; October 2017 in each case). That window is the discount part, which a net cap does
  not reach.
- **PRORATA with the zero caps is harmful.** It deletes the muni shorts and leaves the
  longs, so the book runs net long 15 to 18% of capital and its NAV part's worst window
  grows to −5.4 (March 2020).
- **Hard neutrality here costs 0.04 of Sharpe, not 0.15.** The old figure was on another
  universe and spec; it is not reproduced and not contradicted.

**Turnover.** Every non-REGROSS cap lowers turnover by 19 to 41%, outside the desk's 5%
tolerance. With the band narrowed until turnover matches (a derived width, 2.4% and 3.4%
against the spec's 4.8%):

| at matched turnover (22.5 a year) | Sharpe | return / vol | worst 34: NAV | worst 34: book |
|---|---:|---:|---:|---:|
| uncapped, spec band | 1.15 | 7.60 / 6.60 | −3.52 | −7.75 |
| F25 PRORATA | 1.21 | 6.49 / 5.38 | −2.62 | −8.47 |
| F25 NEUTRAL | 1.23 | 7.07 / 5.77 | −3.17 | −8.35 |
| **uncapped × 0.79, band narrowed the same way** | 1.20 | 6.32 / 5.25 | −2.98 | −6.36 |
| **uncapped × 0.87, band narrowed the same way** | 1.18 | 6.80 / 5.75 | −3.21 | −6.87 |

The last two rows are from `checks.py` and were not pre-specified. They are the answer: a
plain cut in size, given the same narrower band, scores the same Sharpe as the cap and has
a worst book window two points smaller.

**Cost grid, the real-money view** (net Sharpe at 5 / 15 / 30bp, spec band): uncapped 0.98 /
0.64 / 0.13; F25 PRORATA 0.98 / 0.70 / 0.27; F25 NEUTRAL 1.03 / 0.71 / 0.23. The capped
books look better at high cost only because they trade less; no sign flips.

**Under the live gross ceiling** (`band_gross_capped`, 1.80×): uncapped 1.19, F25 PRORATA
1.14, P75 PRORATA 0.91, MED PRORATA 0.81. Same order.

## Controls [V]

| F25 PRORATA against | Sharpe | worst 34: NAV | worst 34: book |
|---|---:|---:|---:|
| the cap, real groups | 1.13 | −3.00 | −8.19 |
| uncapped book at the same mean gross (× 0.79) | 1.15 | −2.80 | −6.16 |
| 200 random groupings, median (5th to 95th) | 1.14 (0.96 to 1.27) | −3.48 (−6.00 to −3.07) | −6.93 (−8.19 to −4.57) |

- The real groups cut the NAV part's worst window by more than 98.5% of random groupings
  do, so the group labels carry something. Per unit of gross it is 87.5%.
- But the plain size cut cuts the NAV window as far (−2.80) and the book window much
  further, and the real grouping's book window is worse than 92% of the random ones.

## Checks that were not pre-specified (`checks.py`) [V]

**The 25% cap on the muni group alone**, which is the motivation taken literally:

| | Sharpe | return | worst 34: muni NAV part | worst 34: NAV part | from 2020: Sharpe | difference from uncapped |
|---|---:|---:|---:|---:|---:|---:|
| uncapped | 1.15 | 7.60 | −3.62 | −3.52 | 1.42 | |
| muni 25%, PRORATA | 1.09 | 7.14 | −3.21 | −3.52 | 1.29 | −0.46 a year (t −3.18) |
| muni 25%, NEUTRAL | 1.13 | 7.36 | −3.21 | −3.52 | 1.38 | −0.24 a year (t −1.72) |

It trims the muni group's own worst NAV window by a ninth, leaves the book's worst NAV
window (March 2016, not a muni event) and worst drawdown where they were, and gives up
return that is distinguishable from zero.

**From 2020 only**, when the muni group is in the book: uncapped 1.42; F25 PRORATA 1.28
(−2.68 a year, t −2.80); F25 NEUTRAL 1.32 (−1.97, t −2.28). Worst NAV window −3.09 against
−3.00 and −2.97. The cap costs most in exactly the years it is meant for.

**The panel's last 12 sessions** (2026-09-29 to 10-14, backtest, not the account): the
uncapped book's muni net averaged −0.33 and reached −0.53; under F25 PRORATA −0.17 and
−0.25. NAV part over those sessions −2.84% uncapped, −0.83% F25 PRORATA, −1.62% muni-only
cap. So a cap would have roughly halved the live muni NAV loss [U: the panel ends before
most of the live window, and the backtest book is not the account's]. It would also have
cut the muni discount gain the account booked over the same weeks.

## Guards

- **Lookahead:** the caps act on targets decided at t; MED and P75 are constants estimated
  on 2013–19 and applied to it (a quantile, not an optimum); XP75 reads nets strictly before
  t (asserted) and agrees with P75. F25 estimates nothing.
- **Stale prices, bounce, ex-dates:** not at issue; this changes sizes inside an existing
  daily book on 13 funds, it adds no event and no new name.
- **Liquidity:** the 13 funds are the deployed universe, selected by the spec's ADV floor.
  No closing spreads were read; the cost grid above stands in for them.
- **Selection:** 12 pre-specified variants plus two reference rows were run once. The
  muni-only cap and the scaled matched rows came after and are labelled.

## What I conclude

1. **Do not add a group cap.** The trade-off the brief asked for, measured: F25 gives up
   0.8 to 1.6 points of return a year to cut the NAV part's worst 34 sessions from −3.5% to
   −3.0%, and the same cut comes from running the book 13 to 21% smaller without touching
   the signal. The whole book's worst window is no better.
2. **The muni-only cap is the cheapest form and still not worth it:** 0.24 to 0.46 a year
   for a ninth off the muni group's own worst window and nothing off the book's.
3. **History-derived caps cannot be used for the muni group:** it has no pre-2020 history
   in this book, and a zero cap that removes the shorts leaves a net-long book with a worse
   tail.
4. **If the October loss is judged too large for the account, the lever is size**
   (`sizing_multiplier`), which is the team lead's decision and already exists. The NAV
   loss was a 0.4%-of-windows draw from a part of the book that averages zero.
5. Nothing here runs as a shadow book; it was a sizing question about the deployed one.

## What would reopen it

- A second 34-session NAV loss of this size in the muni group within a year: the backtest
  says such windows are 0.5% of history, and two would say the backtest's tail is too thin.
- More muni funds in the universe. With two funds the group net is nearly the group gross,
  so a cap is a position limit on two names; with five or more a NEUTRAL cap could trim the
  group view and keep the within-group spreads.
- Real-money costs near 30bp, where any lower-turnover variant gains; that is a band and
  size question first.

## Not done

- The live window itself (the panel ends 2026-10-14).
- Closing bid-ask spreads for the 13 funds.
- A cap on the held book after the band, or one keyed to group NAV volatility rather than
  weight.

**Not independently reviewed.**
