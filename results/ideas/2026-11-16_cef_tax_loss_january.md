# Idea card — Year-end tax-loss selling in closed-end funds: the losers do not rebound more than the rest; the whole CEF market does rise

**Slug:** `cef_tax_loss_january` · **Started:** 2026-11-16, **interrupted** that day about
20 minutes in (the editor was force quit) and **completed 2026-11-18** ·
**Status:** SET ASIDE. The pre-specified book (worst fifth of funds on the year, against all
funds, tenth December session to tenth January session) earned +0.50% a season, t 0.97,
positive in 14 of 25 seasons, +0.16% (t 0.40) without 2008, and no better than its
controls. One lead is left, not pre-specified: all funds together rose 4.0% over the window
in 24 of 25 seasons ·
**Reproducer:** `QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_cefs.py`, then
`QUANTT_ENV_FILE=<env> python3 results/ideas/cef_tax_loss_january/stage.py`, then
`python3 results/ideas/cef_tax_loss_january/explore.py` and `checks.py` ·
**Panels:** CRSP closed-end funds, dead ones included, daily to **2025-12-31**; CRSP closing
bid, ask and volume for the same rows to **2025-12-31** (staged 2026-11-18); CRSP common
stocks ranked to 4,500 to **2025-12-31**; IWM and SPY total returns from Yahoo (fetched
2026-11-10); PCEF from Yahoo, 2010-02-19 to 2026-11-18 (fetched 2026-11-18). Licensed rows
are not in the repository. Every figure below is [V], computed on 2026-11-18, unless tagged.

## The interruption, and what was done after it

- On disk from 2026-11-16: `stage.py`, `explore.py` (complete, with the rule in its
  docstring), and a **zero-byte** `cef_quotes.parquet`. No `results.json`, no card, no PCEF
  file: the first run was killed while staging quotes, so no return had been read.
- **The rule in the `explore.py` docstring is unchanged, word for word.** `explore.py` was
  not edited and was run once.
- **Fix after the interruption (`stage.py` only):** the staging step accepted the zero-byte
  file as already staged. It now deletes an empty file and writes under a `.part` name that
  is renamed when complete. The rebuilt file has 3,765,801 rows, the same count as the CEF
  panel.
- `checks.py` was written after the result was read. Nothing in it is pre-specified.

## The idea

Closed-end funds are held almost wholly by taxable individuals. A fund down on the year is
sold in November and December to realise the loss, no institution takes the other side, and
the price comes back in January. The desk looked at this once before for the 13-fund core
book and found the loser-to-winner gradient in other months too, on 9 seasons
(`docs/RESEARCH_STATE.md`, CORE-b, 2026-10-12). This is the wide test: every CEF, 25 seasons.

## What was fixed before any return was read

- **Universe:** every CRSP closed-end fund; at formation price ≥ $2 and 21-session mean
  dollar volume ≥ $500,000 (also shown at $100,000).
- **Formation F:** the close of the tenth session of December, formation years 2000 to 2024.
- **Signal:** CRSP total return from the year's first session to F.
- **Book:** long the worst fifth, equal weights, against all eligible funds equally weighted;
  separately against the best fifth. Decided at F, bought at the F+1 close, sold at the
  close of the tenth January session (primary) and at January's last close.
- **Headline:** one buy-and-hold figure a season, 25 figures.
- **Controls:** the same sort formed mid-February and held to mid-March; the same rule on
  common stocks ranked 1,501 to 4,000; the worst fifth on the last 63 sessions instead.
- **Variant named in advance:** formation at November's last session.
- **Expected:** losers beat the CEF market by more than a round-trip spread in most years;
  placebo near zero; small caps smaller. **None of the three held.**

## What it showed (gross, no costs)

About 300 funds are eligible a season and 60 are held.

| one figure a season, worst fifth less all eligible | mean | median | t | seasons up | halves | 2002–08 | 2009–15 | 2016–19 | 2020–22 | 2023–24 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Fixed book, to the 10th January session** | **+0.50%** | +0.34% | **0.97** | **14 / 25** | +0.56 / +0.44 | +0.91 | −0.46 | +1.95 | +0.36 | −0.48 |
| held to January's last session | +0.92% | +0.08% | 1.62 | 13 / 25 | +1.20 / +0.67 | +1.19 | +0.72 | +1.65 | −0.21 | −0.33 |
| against the best fifth (needs borrow) | +0.15% | | 0.16 | 12 / 25 | | | | | | |
| $100,000 floor (495 eligible, 99 held) | +0.42% | +0.62% | 1.12 | 15 / 25 | +0.43 / +0.42 | +0.58 | −0.43 | +1.55 | +0.60 | −0.30 |
| variant: formed at November's end | +0.09% | +0.41% | 0.11 | 13 / 25 | +0.16 / +0.01 | −0.61 | −1.36 | +2.19 | +0.74 | −0.41 |
| control: placebo, mid-February to mid-March | −0.69% | −0.01% | −0.92 | 12 / 25 | −1.42 / −0.03 | −1.29 | +0.97 | −3.02 | +0.82 | +0.37 |
| control: small-cap stocks, same rule (244 held) | +0.91% | +1.07% | 1.11 | 16 / 25 | +1.44 / +0.41 | +0.19 | −0.27 | +3.29 | −0.82 | +0.11 |
| control: worst fifth on three months | +0.58% | +0.35% | 0.94 | 17 / 25 | +0.93 / +0.25 | +1.33 | −0.90 | +1.80 | −0.08 | −0.12 |
| fixed book less small caps | −0.40% | | −0.68 | 11 / 25 | | | | | | |
| fixed book less the three-month sort | −0.08% | | −0.25 | 10 / 25 | | | | | | |
| losers against PCEF (2010 on) | +0.77% | +1.03% | 1.08 | 12 / 15 | −0.25 / +1.66 | n/a | −0.34 | +2.58 | +1.01 | +0.11 |
| losers against IWM | +2.61% | +2.52% | 2.08 | 19 / 25 | +3.49 / +1.81 | +6.30 | −0.26 | +3.71 | −1.33 | +3.52 |

Eras are by formation year. The losers rose 4.53% over the window (21 of 25 seasons) and
all eligible funds rose 4.03%: almost all of what the losers earn is what every fund earns.

**Every season, %** (formation year; held to the tenth January session unless said):

| year | eligible | held | cut-off, return on the year | losers | all funds | losers − all | to January's end | losers − best | placebo | small caps | 3-month losers | losers − PCEF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2000 | 104 | 20 | −6.9 | 10.65 | 8.27 | +2.39 | +5.60 | +7.32 | −7.99 | +9.03 | +4.47 | |
| 2001 | 84 | 16 | −3.3 | 3.66 | 4.53 | −0.87 | −1.24 | −1.46 | +1.80 | +3.25 | +0.19 | |
| 2002 | 83 | 16 | −14.0 | 4.39 | 3.73 | +0.65 | −3.53 | +0.33 | −2.15 | +4.29 | −1.63 | |
| 2003 | 137 | 27 | +8.1 | 3.97 | 5.97 | −2.00 | −1.08 | −7.10 | +1.81 | −1.98 | −2.27 | |
| 2004 | 197 | 39 | +2.0 | 1.29 | 0.95 | +0.34 | +0.92 | +1.27 | +0.08 | −2.86 | +0.83 | |
| 2005 | 236 | 47 | −6.4 | 6.38 | 5.46 | +0.92 | −0.00 | −0.66 | −0.91 | +0.38 | +0.88 | |
| 2006 | 292 | 58 | +8.9 | 0.64 | 1.17 | −0.53 | −0.86 | −1.60 | +0.44 | −1.56 | +0.33 | |
| 2007 | 338 | 67 | −15.6 | 2.22 | 3.93 | −1.71 | +3.70 | −0.69 | −1.34 | −3.87 | −0.11 | |
| 2008 | 277 | 55 | −56.3 | 30.27 | 21.60 | +8.67 | +9.20 | +14.75 | −6.97 | +6.95 | +11.31 | |
| 2009 | 295 | 59 | +27.7 | 3.21 | 3.45 | −0.24 | +0.08 | −1.00 | −3.28 | +0.69 | +0.65 | |
| 2010 | 376 | 75 | +0.0 | −0.85 | 1.97 | −2.82 | −1.16 | −5.23 | +0.87 | +0.32 | −4.99 | −4.07 |
| 2011 | 305 | 61 | −11.2 | 7.19 | 5.23 | +1.96 | +2.76 | +3.63 | +0.66 | +2.70 | +1.52 | +2.48 |
| 2012 | 396 | 79 | +8.7 | 5.55 | 4.63 | +0.92 | +1.11 | +0.94 | −0.59 | −0.88 | +1.15 | +1.84 |
| 2013 | 407 | 81 | −17.5 | 6.39 | 4.52 | +1.87 | +3.44 | +2.17 | +0.83 | +1.07 | −0.09 | +2.29 |
| 2014 | 404 | 80 | −4.9 | 2.80 | 2.70 | +0.11 | −0.43 | −1.15 | −0.22 | −1.65 | +0.34 | +1.03 |
| 2015 | 370 | 74 | −16.8 | −7.84 | −2.82 | −5.02 | −0.74 | −9.13 | +8.52 | −4.13 | −4.88 | −5.61 |
| 2016 | 395 | 79 | +0.6 | 3.72 | 3.98 | −0.26 | −0.60 | −0.63 | −0.01 | +1.27 | +0.54 | +0.32 |
| 2017 | 376 | 75 | +1.8 | 5.47 | 2.36 | +3.11 | +3.04 | +1.57 | −1.37 | +4.76 | +1.07 | +3.70 |
| 2018 | 397 | 79 | −14.9 | 10.00 | 6.49 | +3.51 | +5.25 | +4.76 | +0.34 | +4.75 | +3.95 | +4.48 |
| 2019 | 342 | 68 | +13.4 | 4.67 | 3.25 | +1.42 | −1.06 | +1.66 | −11.03 | +2.38 | +1.66 | +1.82 |
| 2020 | 355 | 71 | −9.9 | 4.85 | 2.69 | +2.17 | +0.12 | +1.79 | +3.49 | +1.32 | −1.55 | +3.34 |
| 2021 | 323 | 64 | +5.6 | −0.53 | 1.62 | −2.15 | −2.23 | −5.83 | −1.46 | −10.08 | +0.35 | −1.20 |
| 2022 | 346 | 69 | −24.6 | 4.77 | 3.72 | +1.05 | +1.50 | +1.17 | +0.42 | +6.30 | +0.97 | +0.89 |
| 2023 | 339 | 67 | +1.8 | 0.56 | 1.18 | −0.62 | −0.77 | −1.49 | −0.01 | −1.94 | +0.34 | +0.12 |
| 2024 | 327 | 65 | +7.4 | −0.27 | 0.08 | −0.35 | +0.11 | −1.66 | +0.76 | +2.16 | −0.59 | +0.09 |

"Cut-off" is the best return on the year among the funds held: in up years (2003, 2006,
2009, 2012, 2019, 2024) most of the "losers" were up on the year.

**Per fund held (1,491 fund-seasons), return less all eligible funds:**

| | mean | median | share positive | t, clustered by season | 5th / 25th / 75th / 95th percentile |
|---|---:|---:|---:|---:|---|
| to the 10th January session | +0.50% | −0.02% | 49.7% | 0.91 | −8.1% / −2.3% / +2.7% / +10.3% |
| to January's last session | +1.04% | +0.16% | 51.5% | 1.94 | −7.2% / −2.5% / +3.7% / +11.2% |

The typical held fund does not beat the market. The mean comes from the right tail.

**Mean excess by fifth of the year's return** (1 = worst): +0.50%, −0.30%, −0.42%, −0.14%,
+0.35%. By tenth, the best tenth is the highest at +0.83%. It is a shallow U, not a line
from losers to winners.

**Calendar-time book on the harness** (`harness.evaluate`, shift(2), one unit long against
one unit of all funds, in the market about 20 sessions a year; eras here are by calendar
date, so formation 2015's loss falls in 2016):

| sample | return / yr | vol / yr | Sharpe | t |
|---|---:|---:|---:|---:|
| full, 2000-12 to 2025-03 | 0.48% | 2.55% | 0.19 | 0.93 |
| early half / late half | 0.54% / 0.42% | 2.42% / 2.68% | 0.22 / 0.16 | 0.77 / 0.55 |
| 2002–08 / 2009–15 / 2016–19 / 2020–22 / 2023–25 | | | 0.24 / 0.40 / −0.22 / 0.19 / 0.09 | |
| held to January's end | 0.91% | 3.19% | 0.28 | 1.40 |
| control: placebo, February to March | −1.00% | 2.77% | −0.36 | −1.78 |
| control: worst fifth on three months | 0.53% | 2.49% | 0.21 | 1.05 |

Turnover 3.1 times notional a year. The calendar book and the buy-and-hold figures agree
here, so daily reweighting is not flattering anything.

**Liquidity and spread of what is held:** median 21-session dollar volume $1.29M ($1.46M
from 2016), median price $11.59, median closing bid-ask spread at entry 18bp (mean 33bp;
17bp from 2016), 18bp at exit. No held fund lacked volume on its entry day; one in 1,491
had stopped trading by the exit. A round trip costs about one spread, 18bp, against a mean
of 50bp and a median fund of −2bp.

## Checks

Pre-specified:

- **Mid quotes.** 99.7% of held funds have a two-sided closing quote at both ends. On that
  sample the spread is +0.52% on closes and +0.50% on mids (t 0.98). Held funds closed
  1.6bp below the mid at entry and 1.8bp above it at exit; all funds 0.2bp below and 2.2bp
  above. Bid-ask bounce is not in this result, in either direction.
- **Skip day** (entry one session later): +0.33%, t 0.68, 14 of 25.
- **Ex-dates.** Held funds had 0.80 ex-dates in the holding window and all funds 0.86, so
  the desk's ex-date drift does not differ between the two legs. Returns are CRSP total
  returns.
- **Survivorship.** None in the CEF legs: dead funds are in the panel.

Not pre-specified (`checks.py`, written after the result was read):

| | mean | t | seasons up |
|---|---:|---:|---:|
| fixed book without formation 2008 | +0.16% | 0.40 | 13 / 24 |
| the same, held to January's end | +0.58% | 1.23 | 12 / 24 |
| funds actually down on the year, less all (115 funds, 23 seasons with 10 or more) | +0.38% | 1.14 | 15 / 23 |
| funds down more than 10%, less all (98 funds, 14 seasons) | +0.77% | 1.33 | 11 / 14 |
| fixed book in the 6 seasons when the median fund was down on the year | +1.39% | 0.73 | 4 / 6 |
| fixed book in the other 19 | +0.22% | 0.60 | 10 / 19 |
| cross-section a season on both ranks: slope on the year's rank | +2.5% | 1.78 | 16 / 25 |
| slope on the three-month rank | −3.1% | −1.40 | 8 / 25 |

The sign of the year's-rank slope is the wrong way for the idea: holding the three-month
return fixed, funds that did better on the year did better in the window.

**The level, not the spread** (not pre-specified; the largest number in the table):

| all eligible funds, equal weights, F+1 close to the 10th January session | mean | median | t | seasons up | 2002–08 | 2009–15 | 2016–19 | 2020–22 | 2023–24 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | +4.03% | +3.72% | 4.67 | 24 / 25 | +6.12 | +2.81 | +4.02 | +2.67 | +0.63 |
| less SPY | +2.88% | +2.25% | 2.78 | 20 / 25 | +6.08 | +0.96 | +1.48 | +1.43 | +1.12 |
| less IWM | +2.11% | +1.67% | 2.06 | 16 / 25 | +5.39 | +0.20 | +1.76 | −1.69 | +4.01 |
| less IWM, without 2008 | +1.39% | +1.43% | 1.84 | 15 / 24 | +3.03 | +0.20 | +1.76 | −1.69 | +4.01 |
| less PCEF (2010 on; equal weights against the ETF's own weights) | +0.44% | +0.58% | 2.62 | 12 / 15 | n/a | +0.16 | +0.63 | +0.65 | +0.59 |

The same "all funds less IWM" over the same-length window started at the tenth session of
each month, 2001 to 2024: December +2.15% (t 2.01, 15 of 24), October −1.77% (t −2.20, 6 of
24), November −0.99% (t −1.16), July +1.23% (t 1.60), every other month within ±0.6%. That
is twelve looks, so a t of 2 in one of them is close to what chance gives; what speaks for
it is that the two months before are the two worst. Funds lag stocks from mid-October to
mid-December and recover from mid-December to mid-January. That is what market-wide
year-end selling by individuals would look like. It is not beta-adjusted (CEFs are mostly
bond funds, so one unit of IWM over-hedges), and it is weak in 2009–15 and negative in
2020–22 against IWM.

## What I conclude

1. **The cross-sectional idea is not there.** The worst fifth beat all funds by 0.50% a
   season with a t under 1, the median held fund did not beat the market, formation 2008
   alone is 8.67 of the 12.5 points the 25 seasons sum to, and without 2008 the mean is 0.16%.
2. **No control is beaten.** Small-cap stocks under the same rule score higher (+0.91%), so
   nothing here is special to closed-end funds. The three-month sort scores the same
   (+0.58%), so what there is cannot be told from ordinary reversal. Only the
   February-to-March placebo is lower (−0.69%), and the difference (1.19%, t 1.07) is not
   reliable.
3. **It is not a quote artifact, and it is not thin.** Mids give the same answer, spreads
   are 18bp, held funds trade $1.3M a day. The idea fails on the returns themselves.
4. **Forming earlier is worse** (+0.09% from November's end): the losers go on losing into
   mid-December.
5. **What moves is the whole fund market.** All funds rose 4.0% over the window in 24 of
   25 seasons, 2.9% more than SPY. A long-only book (PCEF, or a basket of liquid funds)
   bought at the eleventh December session and sold at the tenth January session needs no
   borrow. It was found after the fact, in one of twelve calendar windows, and is not
   pre-specified; it is a lead, not a result.
6. **Not a shadow book as specified.** Nothing about the loser sort would add to a plain
   long position in funds over the same four weeks.

## What the rule would hold this December

No list is given: CRSP ends 2025-12-31 and no 2026 price has been read. The procedure, on
a live daily feed (Alpaca daily bars with dividends, or the CRSP panel once it is extended):

1. At the close of the tenth session of December 2026 (2026-12-14 [U: counted from the
   weekday calendar, no exchange calendar fetched]), take every listed closed-end fund
   priced at $2 or more with 21-session mean dollar volume of $500,000 or more.
2. Rank them on total return since the close of 2026-01-02. Hold the worst fifth, equal
   weights; buy at the 2026-12-15 close; sell at the close of the tenth session of January
   2027 (2027-01-15 [U], same caveat).

For scale, the same procedure on 2025 data (formation 2025-12-12, not scored: no January
2026 in the panel) gives 324 eligible funds and 64 held, cut-off +0.4% on the year, median
−5.4% among those held against +7.1% for all funds, 92% of those held below zero.

## What could not be done

- **Net asset values** were not used. Whether the December fall and January rise are
  discount moves or asset moves is not answered; Yahoo's NAV series cover live funds only.
- **Formation 2025** cannot be scored (no January 2026 in CRSP).
- **The small-cap control** needs a stock to have been in the largest 4,500 all year, so
  stocks that fell out of that panel during the year are missing from its losers. This
  understates how far small-cap losers fell; its direction on the rebound is not known.
- **Borrow** for the loser-against-winner version was not looked at; that version scored
  +0.15% (t 0.16), so it does not matter.

## What would reopen it

- **The market-level effect, written down before a test:** long PCEF (or the equal-weighted
  liquid funds) against a beta-matched mix of SPY and a bond ETF, from the eleventh
  December session to the tenth January session, with every other month as the placebo,
  and with fund NAVs to show whether it is the discount that moves. December 2026 and
  January 2027 would be its first out-of-sample season.
- **A loss measure closer to the taxpayer's:** price below its level at the last several
  year-ends (holders with an actual loss), instead of the return on one calendar year.
  The check on funds down more than 10% (+0.77%, t 1.33, 11 of 14) is not enough to say
  this would work.

**Not independently reviewed.**
