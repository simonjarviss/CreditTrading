# Idea card — Earnings drift in smaller stocks: strong on the long side, where the large-stock version found nothing

**Slug:** `pead_small` · **Written:** 2026-11-15 ·
**Status:** EXPLORE, cleared and independently reviewed. Long-only against IWM: 1.27 gross as
fixed, 1.1 with conservative release timing, about 0.7 with the surprise a free feed can
supply. Not on shadow: it needs a live small-stock panel and an earnings feed ·
**Reproducer:** `python3 scripts/research/stage_crsp_equities.py --top 4500`,
`python3 scripts/research/stage_ibes_surprises.py`, then
`python3 results/ideas/pead_small/explore.py` and `checks.py` ·
**Panels:** CRSP daily (4,500 largest US common stocks each month, delisted names included)
and IBES quarterly surprises on R2, prices to **2025-12-31**, last release 2025-12-29; IWM
total returns from Yahoo (fetched 2026-11-10). CRSP and IBES rows are not in the repository.

## The idea

After an earnings release that beats the analysts' forecasts, a share keeps rising for
weeks. On the 1,500 largest stocks the desk found almost none of this (`pead_wide`, 0.21,
`results/ideas/2026-11-11_pead_wide.md`). Smaller stocks have fewer analysts and fewer
funds able to trade them, and the team lead asked on 2026-11-15 for ideas a small book can
exploit. No return on these stocks had been read.

## What was fixed before the test

- **Universe:** market-value rank 1,501 to 4,000 at the previous month end, price ≥ $5,
  21-session dollar volume ≥ $500,000.
- **Rule:** `pead_wide`'s, imported unchanged. A release is known at the first session at
  whose close it is public. For 40 sessions from then the stock carries its surprise; each
  day the top tenth is held long and the bottom tenth short, equal weights. shift(2): the
  announcement day's own move is never earned.
- **Two sorts:** A, the IBES surprise score (surprise over the analysts' dispersion);
  B, the stock's own two-session announcement move, which had looked better on large
  stocks after the fact (0.73) and for which this universe is a fresh test.
- **The long leg alone against IWM**, the half that needs no borrow, and the short leg alone.
- **Control:** each sort 126 sessions late. **Expected:** both positive, B above A.

## What it showed (gross, shift(2), no costs, no borrow) [V]

2000-05-30 to 2025-12-31; 291,872 releases; about 112 names a day (56 long).

| sort A, the analyst surprise | both sides | long leg vs IWM | short leg vs IWM |
|---|---:|---:|---:|
| full sample, Sharpe (t) | 1.30 (6.60) | **1.27 (6.42)** | 0.33 (1.68) |
| early half / late half | 1.29 / 1.33 | 1.45 / 1.06 | 0.10 / 0.57 |
| 2002–08 | 1.74 | 1.65 | 0.57 |
| 2009–15 | 0.77 | 1.18 | −0.16 |
| 2016–19 | 1.54 | 1.40 | 0.65 |
| 2020–22 | 1.27 | 0.54 | 0.83 |
| 2023–25 | 1.54 | 1.50 | 0.46 |
| control: signal 126 sessions late | 0.41 | 0.27 | 0.18 |
| return a year / volatility | 8.8% / 6.8% | 12.8% / 10.1% | 4.0% / 12.1% |

- **The drift is on the long side.** Stocks that beat keep rising; stocks that miss do not
  keep falling by much. The half that needs no borrow carries the result.
- **Sort B failed.** The announcement-move sort is 0.59, −0.06 since 2013, and below its
  own late control (0.68). The expectation "B above A" was wrong, and the large-stock
  variant it came from is not confirmed.
- **Capacity:** at $1M the median position is 0.14% of the name's daily volume and the
  95th percentile 1.1%; at $5M, 0.7% and 5.7%.

## Independent review, 2026-11-15, and the checks stored from it (`checks.py`) [V]

A quant-reviewer re-derived the long leg from the rule with its own code: Sharpe 1.26
(t 6.39), identical to this script's series on 6,435 of 6,437 days. It found no lookahead:
the rank is the previous month end's (0 violations in 1.28M name-months), the filters are
dated at the decision, and entries into the long tenth are not selected on later splits.

| long leg | Sharpe (t) | halves | 2023–25 |
|---|---:|---:|---:|
| as fixed, less IWM | 1.27 (6.42) | 1.45 / 1.06 | 1.50 |
| less the equal-weighted return of its own universe | 1.37 (6.90) | 1.44 / 1.29 | 2.22 |
| signal started one / two sessions later | 1.13 / 1.00 | | 1.48 / 1.49 |
| every release treated as known the session after its date | 1.12 (5.65) | 1.24 / 0.98 | 1.44 |
| **what a free feed can sort on: surprise ÷ consensus, that later timing** | **0.68 (3.41)** | 0.81 / 0.52 | 0.92 |
| rank 1,501–2,500 / 2,501–4,000, each less its own universe | 0.92 / 0.67 | | 1.48 / 1.68 |

- **The hedge is not the source.** The universe itself earns 0.16 against IWM [S: review];
  measured against its own universe the leg is higher, not lower.
- **Release times before 2009 are doubtful** [S: review]: stocks with a pre-open time stamp
  in 2000–08 still gained 77bp two sessions later, as if some had really reported after the
  close. Treating every release as a session later removes the question: 1.12.
- **It decays smoothly with delay** [S: review]: 1.12, 0.99, 0.77, 0.59 and 0.36 when the
  signal starts 1, 2, 5, 10 and 20 sessions late. A third of the excess return is earned in
  the first five sessions held.
- **The score leans on analysts who agree** [S: review]: half the long tenth has a
  dispersion of one cent or less. Flooring the dispersion at 2 cents gives 1.09, at 5 cents
  0.76. Sorting on surprise over consensus, which needs no dispersion, gives 0.68 here
  (the review measured 0.87 without the later timing). Drift is present under every scaling
  and 1.3 is the best of them.
- **A step at rank 1,500 with no data cause found** [S: review]: the same long tenth less
  its own universe is 0.15 on ranks 1–500 and 0.07 on 501–1,500.
- **Survivorship** [S: review]: delisted names are in the panel; the long leg held 96
  name-days with no row in 360,767 (49 exits, all looking like completed mergers). Whether
  the staging keeps CRSP's delisting row could not be checked without R2.
- **Real-money view, kept apart from the gross figures:** the long leg turns over 41 times
  a year. At 5 / 15 / 30bp per unit traded on the stock side it is 1.06 / 0.65 / 0.03. The
  sign does not flip, and the result is gone at 30bp. What these stocks cost to trade at
  the close is not measured.

## What I conclude

1. Earnings drift is alive in stocks ranked below 1,500 and is earned on the long side, in
   every era, including 2023–25.
2. The honest size depends on the data: about 1.1 to 1.3 with analyst dispersion (IBES,
   licensed, not available live), about 0.7 with the surprise a free source gives.
3. It fits a small book: $1M uses about 0.1% of a day's volume per name.

## Next

- **A live version needs two things the desk does not have:** a daily price panel for about
  1,100 small stocks, and an earnings feed. yfinance returns the estimate, the reported
  figure and a timed release for covered small stocks (read for three names on 2026-11-15:
  two had current rows, one had none since 2014); it has no bulk calendar, and Nasdaq's
  public calendar refused this machine (HTTP 403). The shadow book is a build, not a switch.
- The free-feed sort (0.68) is the one to carry into that build, with the later timing.
- The announcement-move sort is closed for this universe.
