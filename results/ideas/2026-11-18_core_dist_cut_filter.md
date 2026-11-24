# Idea card — do the live discount books buy a fresh distribution cut, and would holding off help?

**Slug:** `core_dist_cut_filter` · **Written:** 2026-11-18 ·
**Status:** SET ASIDE. The books do buy into a cut (the core's position in the fund rises by
4.1% of capital on average, C4's by 0.8%), but neither book has lost money doing it, and both
fixed hold-off rules LOWER the return of both books in every variant. On the core's 13 funds
there are 38 cuts in 13 years, and those funds do not show the card's post-cut fall at all.
Not a filter for either live book ·
**Reproducer:** `python3 results/ideas/core_dist_cut_filter/explore.py --data <data/cef> --families <data/cef_families>`,
then `python3 results/ideas/core_dist_cut_filter/checks.py` with the same arguments ·
**Panels:** the desk's CEF price and NAV panels, last rows **2026-10-15** (prices) and
**2026-10-14** (NAV; the book's last session); `data/cef_families`, last row **2026-10-09**;
CRSP distributions (`~/quantt_research/cef_dist_changes/raw_dist.parquet`) and the CRSP
closed-end fund panel, both to **2025-12-31**, so no cut after that date is in the test;
`data/cef/cef_distributions.parquet`, last ex-date **2026-09-03**. Every figure is [V],
computed on 2026-11-18 by the two scripts, unless tagged. Gross, shift(2), no costs.

## What was asked

`results/ideas/2026-11-16_cef_dist_changes.md` found that a closed-end fund which cuts its
regular distribution by 5% or more falls 130bp against the CEF market around the announcement
and a further 85bp over 20 sessions and 137bp over 60 (n 2,224) [S: that card]. A cut widens
the discount, and both live books buy funds whose discount has widened. The team lead asked on
2026-11-18 how that research can be used in the live books. This measures whether the books
buy fresh cuts, and what a fixed hold-off would have done. Nothing in the sleeve, the specs,
the book files or `data/` was touched.

**This is a re-test of a dead line and is counted as one.** `docs/RESEARCH_STATE.md` records
"Distribution data: failed twice": as a distribution-cut filter (8 variants run, the 1 that
beat the baseline chosen after looking at all 8) and as a cut term inside the Kalman estimator
(1.60 → 1.28), both on the 17-fund book of the shift(1) era. The present test is the same
family as the first. It differs only in that the event list and the two windows come from an
outside study, two rules were fixed before any return was read and nothing was chosen among
them, and a placebo was fixed with them. It reaches the same answer.

## What was fixed before any return was read (`explore.py` docstring)

- **Books.** Core: the frozen spec's `build_targets` and `band(T, BAND_WIDTH)`, unchanged, as
  in `core_group_cap`; price returns; from the first held session, 2013-06-25. C4: the same
  functions on the families panels with the C4 spec's 74 funds and its two masks, which is
  trial 52's z book, from 2005-02-22.
- **Events.** The card's `declarations()` imported, not copied: CRSP regular cash dividend
  down 5% or more, stable base, same frequency, a declaration date, first ex-date of its
  declaration. The card's price and volume filter is not applied; the book's own eligibility
  decides.
- **Mapping.** Desk ticker to the permno carrying that ticker on CRSP's last date, checked on
  returns. Core: every fund correlates at least 0.9955 with the desk's own closes.
- **Timing.** Known at the close of K, one session after the first session on or after CRSP's
  declaration date. The rule changes target rows K to K+H−1, which earn K+2 to K+1+H, the
  card's window. Asserted in code.
- **The rule, two variants, H = 20 and 60, nothing else.** NNL (no new long): the fund's
  target may not rise above the position the unchanged book held at K−1, so a short may not
  be covered either. FLAT: the target is zero. Applied to targets before the band.
- **Controls.** The same rule and the same count of events per fund, at dates drawn from that
  fund's own unchanged declarations (UNCH) and at random sessions (RAND), 200 draws each.
- **Expected.** At most a few basis points a year on the core; inside the placebo band; C4
  the only place a decision could come from.

**Changes made after the first run started, all before the figure they affect was read:**
the first run stopped three times in the C4 mapping check (ADX and GAM correlate 0.948 and
0.949 with CRSP, under my 0.95 bar; the desk's own permno map confirms both; BTX's permno in
the desk map is stale, and the CRSP one correlates 1.000 on 232 sessions), and once in the
UNCH placebo (HQH and HQL have 7 and 9 unchanged declarations against 8 and 10 cuts; the
shortfall is drawn at random sessions). The core block had printed each time and did not
change. One units error was fixed after the first complete run: the two discount columns were
100 times too large. No rule or P&L figure moved (checked: identical before and after).

## Counts

| | core (13 funds) | C4 z book (74 funds) |
|---|---:|---:|
| qualifying cuts while the book is live | **38** on 10 funds | **235** on 58 funds |
| a year | **2.9** | **10.9** |
| by era | 2013–15: 8; 2016–19: 19; 2020–22: 9; 2023–25: 2 | 2005–09: 55; 2010–14: 49; 2015–19: 51; 2020–22: 42; 2023–25: 38 |
| last cut in the list | 2023-03-02 | 2025-12-02 |
| the fund was in the book around the cut | 27 | 120 |
| share of live fund-days the rule touches | 0.7% (H 20) to 2.5% (H 60) | 0.3% to 1.1% |
| median cut | −12.5% | −15.1% |

The desk's own distributions panel has ex-dates and amounts only, no declaration date. All 38
core cuts are in it at the same ex-date with a fall of 5% or more, so it agrees with CRSP on
every one. It shows 2 raw falls of 5% or more after CRSP ends (no stable-base rule applied, so
these may be cuts back from specials); they are not in the test.

## (1) Does the book buy fresh cuts?

Yes. K−3 is the last decision before the announcement window; "unchanged" is the same funds'
declarations with no change in the amount.

| | core, cuts | core, unchanged | C4, cuts | C4, unchanged |
|---|---:|---:|---:|---:|
| n | 38 | 1,253 | 235 | 5,810 |
| price less the book's universe, announcement window | −215bp (t −2.9) | | −83bp (t −3.9) | |
| discount, K−3 to K | −2.31pp (t −3.2) | +0.57pp | −0.83pp (t −3.9) | +0.10pp |
| z-score, K−3 to K | −0.42 (t −3.3) | +0.18 | −0.23 (t −3.4) | +0.05 |
| mean position at K−3 → K → K+5, % of capital | −1.63 → +1.35 → +2.46 | +0.61 → +0.47 → +0.53 | +0.31 → +0.79 → +1.15 | −0.18 → −0.14 → −0.21 |
| position change K−3 to K+5 | **+4.09 (t 2.3)** | −0.08 (t −0.5) | **+0.83 (t 3.5)** | −0.04 (t −0.8) |
| bought more / sold | 10 / 1 | 151 / 158 | 30 / 12 | 546 / 587 |
| held short / long / flat at K−1 | 13 / 14 / 11 | | 59 / 61 / 115 | |

- **The core funds that cut were, on average, held SHORT before the cut** (−1.6% of capital):
  they were rich. The cut knocks the price down, the short is covered and in 10 of 38 cases
  the book goes further and buys. Only 1 was sold.
- The median change is zero in both books: most cuts move the target by less than the band.

**And did that cost the book?** No, on neither book.

| per cut, bp of the book's capital | core, 20 | core, 60 | C4, 20 | C4, 60 |
|---|---:|---:|---:|---:|
| book's P&L in the cut fund | +10.9 (t 0.7) | +16.7 (t 0.8) | +1.8 (t 0.5) | +2.0 (t 0.5) |
| less the same fund's usual P&L over as many sessions | +6.5 (t 0.4) | +3.0 (t 0.1) | +0.4 (t 0.1) | −2.3 (t −0.6) |
| where the book was long over the window | +8.5 (n 18, t 0.6) | +38.2 (n 22, t 1.1) | −1.7 (n 71, t −0.3) | +1.5 (n 72, t 0.2) |
| where it was short | +29.2 (n 9) | −41.1 (n 5) | +10.5 (n 51) | +7.2 (n 50) |
| mean position held in the window, % of capital | +2.7 | +4.0 | +1.2 | +1.3 |

**The card's effect on the desk's own funds.** The fund after the cut, K+2 onward:

| | core, 20 | core, 60 | C4, 20 | C4, 60 |
|---|---:|---:|---:|---:|
| price return less the book's universe (desk panels, price only) | +20bp (t 0.3) | −15bp (t −0.2) | **−110bp (t −3.0)** | **−204bp (t −3.6)** |
| NAV return less the universe | +28bp (t 1.0) | +41bp (t 0.9) | −29bp (t −0.9) | −64bp (t −1.2) |
| discount change less the universe | +10bp (t 0.2) | −44bp (t −0.6) | **−87bp (t −3.2)** | **−150bp (t −4.6)** |
| the card's own method (CRSP total return less the CEF market), every cut of these funds since 2000 (`checks.py`) | −6bp (n 60, t −0.1) | +18bp (t 0.3) | −43bp (n 215, t −1.1) | −133bp (t −1.6) |
| the card, every CRSP fund (reproduced exactly by `checks.py`) | −85bp (n 2,224, t −5.5) | −137bp (t −4.8) | | |

- **New, and the card could not do it: on the C4 funds the fall after a cut is the DISCOUNT
  widening further, not the NAV.** That is the half of the card's finding that a discount book
  would care about.
- **On the core's credit and muni funds there is no further fall.** 60 cuts since 2000 by the
  card's own method give −6bp and +18bp. With 60 events the standard error is about 45bp, so
  this cannot exclude the card's −85bp either [U].
- The price-only rows flatter the fall a little: a cut fund usually still yields more than its
  peers, and price returns leave the yield out. The discount row does not have that problem.

## (2) The rule

Plain band at the spec's width, gross. "Difference" is the daily P&L of the rule less the
unchanged book, annualised.

**Core, 2013-06-25 to 2026-10-14**

| | Sharpe | return | vol | worst drawdown | turnover (change) | halves | difference, bp a year (t) |
|---|---:|---:|---:|---:|---:|---:|---:|
| unchanged | 1.15 | 7.60% | 6.60% | −14.4% | 22.5 | 0.87 / 1.45 | |
| NNL, 20 | 1.04 | 7.03% | 6.75% | −15.9% | 22.4 (−0.5%) | 0.72 / 1.39 | **−57 (−1.1)** |
| NNL, 60 | 0.91 | 6.21% | 6.79% | −19.0% | 22.2 (−1.1%) | 0.48 / 1.39 | **−140 (−2.2)** |
| FLAT, 20 | 1.11 | 7.24% | 6.53% | −14.4% | 22.5 (−0.1%) | 0.82 / 1.40 | **−36 (−1.1)** |
| FLAT, 60 | 1.08 | 6.94% | 6.42% | −14.1% | 22.2 (−1.2%) | 0.71 / 1.48 | **−66 (−1.4)** |

| Sharpe by era (difference, bp a year) | 2013–15 | 2016–19 | 2020–22 | 2023–26 |
|---|---:|---:|---:|---:|
| unchanged | 1.39 | 0.56 | 1.01 | 1.79 |
| NNL, 20 | 1.48 (+95) | 0.26 (−192) | 0.89 (−77) | 1.79 (0) |
| NNL, 60 | 1.19 (−102) | 0.04 (−341) | 0.89 (−78) | 1.79 (0) |
| FLAT, 20 | 1.48 (+54) | 0.41 (−102) | 0.91 (−74) | 1.80 (+3) |
| FLAT, 60 | 1.39 (−4) | 0.29 (−183) | 1.00 (−65) | 1.82 (+15) |

**C4 z book, 2005-02-22 to 2026-10-09** (price returns on today's 74 funds, so its level is
not trial 52's figure; only the differences matter here)

| | Sharpe | return | vol | worst drawdown | turnover (change) | halves | difference, bp a year (t) |
|---|---:|---:|---:|---:|---:|---:|---:|
| unchanged | 1.34 | 9.55% | 7.13% | −10.5% | 39.6 | 1.16 / 1.49 | |
| NNL, 20 | 1.34 | 9.53% | 7.14% | −10.5% | 39.3 (−0.8%) | 1.21 / 1.45 | −2 (−0.1) |
| NNL, 60 | 1.24 | 8.97% | 7.26% | −10.3% | 38.6 (−2.5%) | 1.04 / 1.41 | **−58 (−1.5)** |
| FLAT, 20 | 1.32 | 9.35% | 7.07% | −11.3% | 39.2 (−1.0%) | 1.23 / 1.41 | −20 (−0.9) |
| FLAT, 60 | 1.25 | 8.93% | 7.13% | −9.9% | 38.3 (−3.2%) | 1.07 / 1.41 | **−62 (−1.9)** |

| difference by era, bp a year | 2005–09 | 2010–14 | 2015–19 | 2020–22 | 2023–26 |
|---|---:|---:|---:|---:|---:|
| NNL, 20 | +5 | +49 | −23 | −57 | −8 |
| NNL, 60 | −95 | −56 | −13 | −25 | −97 |
| FLAT, 20 | +26 | +48 | −35 | −187 | −18 |
| FLAT, 60 | −86 | −28 | −30 | −161 | −43 |

- **Turnover moves by 3.2% at most**, inside the desk's 5%, so no band width was re-derived
  and the comparison stands as it is.
- **Does it flip by era?** The 60-session rules are negative in every era on C4 and in every
  era with events on the core. The 20-session rules are positive in the earliest era on both
  books and negative after. **2023–26 says nothing on the core**: 2 cuts, both early 2023.
  On C4 it has 38 cuts and every variant is negative.

## Controls

Share of the 200 placebo draws that did as well as or better than the real cuts, with the
placebo's mean difference (bp a year) and its 5th to 95th percentile:

| | core, UNCH | core, RAND | C4, UNCH | C4, RAND |
|---|---|---|---|---|
| NNL, 20 (real −57 / −2) | 98.5%; −4 (−31 to +22) | 99.5%; 0 (−26 to +29) | 66.5%; +2 (−12 to +20) | 45.5%; −4 (−21 to +13) |
| NNL, 60 (real −140 / −58) | 100%; −7 (−69 to +87) | 100%; −10 (−65 to +49) | 97.5%; −16 (−52 to +22) | 95.0%; −19 (−57 to +18) |
| FLAT, 20 (real −36 / −20) | 83.5%; −9 (−55 to +31) | 83.0%; −7 (−58 to +38) | 66.5%; −14 (−36 to +7) | 72.5%; −13 (−43 to +12) |
| FLAT, 60 (real −66 / −62) | 76.0%; −33 (−117 to +38) | 83.5%; −20 (−110 to +57) | 73.0%; −45 (−95 to +5) | 73.5%; −42 (−101 to +11) |

- **Holding less of a fund at a random date costs a little on its own** (the placebo means are
  negative). The real cuts do no better than that in any variant, and NNL does worse than
  nearly every random draw: on the core, a cut has been a better than average time for this
  book to be buying the fund, not a worse one.
- **Checks named in advance.** Dated from the ex-date (the only form the desk's own panel
  could drive): every variant negative on both books, core −31 to −108bp a year, C4 −22 to
  −54bp. Under the live gross ceiling: core −37 to −143bp, C4 +1 to −62bp. On total returns
  (core): −42 to −192bp (NNL, 60: t −3.0).

**After the fact (`checks.py`, nothing pre-specified, an extra look):**

- **Where the cost sits.** On the core nearly all of it is the 13 cuts where the book was
  short before the cut: NNL, 60 on those alone is −137bp a year (t −2.2), against −6bp on
  the 14 where it was long. Covering a rich fund's short after it cuts, and buying it, is where
  the book has made money. C4 is the same shape (short subset −44bp, long −10bp).
- **A narrower rule, "a short may be covered, no long opened or added to".** Core: −13bp a
  year at 20 sessions (t −0.6), −57bp at 60 (t −1.7; worse than all 200 random draws). C4:
  −3bp (t −0.2) and −39bp (t −1.2). Still no gain.

## What I conclude

1. **The live books do buy into fresh cuts**, measurably: +4.1% of capital on the core and
   +0.8% on C4 within five sessions, against nothing at unchanged declarations.
2. **That buying has not cost either book.** The P&L in the cut fund is slightly positive on
   both, and no different from the fund's usual P&L.
3. **A hold-off after a cut is not worth having on either book.** All eight rule-and-window
   pairs lower the return; none beats its placebo; the after-the-fact narrower rule does not
   either. Recommendation: **do not add it; no `/spec-change`.**
4. **Why the card's result does not carry over.** Two reasons, both measured. On the core's
   funds the post-cut fall is not there (−6bp, n 60). On the C4 funds it is there, and it is
   the discount (−87bp and −150bp), but the book's average position in a cut fund is +1.2% of
   capital, so the drift is worth about 1 to 3bp of capital per cut (1.2% of 87 to 204bp),
   roughly 10 to 30bp a year at 11 cuts a year [U: arithmetic on the rows above, not a
   measured P&L; the measured P&L in cut funds is +2bp per cut]. The rule gives up more than
   that by stopping the book trading the fund on everything else it knows.
5. **Can the sample support a decision?** For the core, only one way. 38 cuts, 27 with the
   fund in the book, 2.9 a year and none since March 2023: far too few to show a gain of a
   few basis points, and enough to say there is no sign of a loss to avoid. For C4, 235 cuts
   (120 with the fund in the book) is enough to say the rule does not help by anything
   worth its complexity; it is not enough to tell −20bp from zero.
6. **Where the card's finding belongs.** As its own list (a short, or an avoid list for a
   long-only sleeve) on equity and multi-asset funds, where the further discount widening is
   real. Not as a gate on a book that already holds each fund at about 1% of capital.

**If a later test did favour a rule**, the live sleeve would need the declared amount within a
session or two. The desk's panel carries ex-dates only (a median 6 to 7 sessions after K), and
the repo's notes say Alpaca files a cash dividend near its payable date with no guarantee on
creation time [S: the `cef_dist_changes` card, citing `quantt/broker/alpaca.py`]; its timing
has not been measured. The change would be a new frozen-spec key, default off, through
`/spec-change` with a byte-for-byte no-op proof. None of that is written here.

## What would reopen it

- A measured loss: the live books losing in cut funds over a year of fills.
- A book that holds single funds at several percent of capital in equity or multi-asset
  CEFs, where a 150bp discount drift is worth more than the trading it blocks.
- The cut list read as a short book on C4-type funds with borrow measured on the day.

## Could not do

- **The live C4 blend (trial 54's level signal, in the spec since 2026-11-03).**
  `c4_paper_benchmark.spec_targets` refuses a panel past 2022-12-30, and building the blend
  another way would be a second copy of it. The z book (trial 52) is what was run. The level
  signal buys a fund cheap against its family, so it may buy cuts harder than the z book; that
  is unmeasured.
- **C4 on total returns.** `total_returns` raises on IGR's 2026-09-08 split, which has no
  recorded ruling for this panel. Price returns only, as the core's baselines.
- **Cuts after 2025-12-31**, where the event list ends. The books run to October 2026.
- **Declaration dates against a second source**, as in the card.
- The licensed per-event rows are not in the repository; `results.json` and `checks.json`
  hold aggregates and counts by fund and year.

**Files:** `results/ideas/core_dist_cut_filter/explore.py`, `checks.py`, `results.json`,
`checks.json`. **Not independently reviewed. No ledger or evidence-log row written (this lane
was told to create only these files).**
