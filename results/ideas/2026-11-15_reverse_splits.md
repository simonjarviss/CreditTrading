# Idea card — Reverse splits: the share keeps falling for a month, and Alpaca will not lend it

**Slug:** `reverse_split_after` · **Written:** 2026-11-15 ·
**Status:** SET ASIDE as a short at Alpaca. The price pattern is strong; the borrow, read on
the names the book would hold today, is not there. What would reopen it is at the end ·
**Reproducer:** `python3 results/ideas/reverse_splits/explore.py`, then `checks.py`, then
`QUANTT_ENV_FILE=<env> python3 results/ideas/reverse_splits/borrow_now.py` ·
**Panels:** CRSP distributions and daily rows on R2 (`scripts/research/stage_crsp_reverse_splits.py`),
ex-dates 2000-01-03 to 2025-12-31, prices to **2025-12-31**; IWM and SPY total returns from
Yahoo (fetched 2026-11-10); Alpaca's corporate-actions feed, asset flags and daily bars read
**2026-11-15**. CRSP rows are not in the repository.

## The idea

A company reverse-splits when its share price is too low, usually to keep its listing. The
date is public and the share has normally fallen a long way already. The desk's catalogue
carried this as card G1 (`results/events/SPECIAL_SITUATIONS_CATALOGUE_CORP_2026-10-15.md`)
and closed it on a borrow count, 54 of 432 active 2025 symbols shortable, without reading a
return and without asking which of those names a book would actually hold. This card reads
the return first and then measures borrow on the right set.

## What was fixed before the test

Only counts had been read: 3,375 reverse splits on common shares since 2000, median ex-day
price $4.08, median ex-day dollar volume $810k.

- **The event:** CRSP distribution type FRS or SP with a price factor between −1 and 0, on
  a share typed common on the ex-date. X is the ex-date.
- **Eligible, at the close of X:** price ≥ $2 and 21-session dollar volume ≥ $500,000.
- **AFTER (the main book):** short the share, long IWM the same size, 10% a name, scaled
  down when a side would pass 50%. Decided at the close of X, filled at the close of X+1,
  earns X+2 to X+21.
- **WAIT:** short from the session after CRSP's declaration date is public to the close of
  X−1.
- **Controls:** the AFTER rule on forward splits, and on the same reverse splits moved 60
  sessions later and 60 earlier.

## What it showed (gross, shift(2), no costs, no borrow) [V]

2000-06-01 to 2025-12-31. AFTER: 1,260 eligible events (49 a year), invested 82% of
sessions, 3.9 names held on average. 110 of 24,974 held name-days had no CRSP return (a
share that had stopped trading) and count as zero.

| AFTER | gross Sharpe (t) |
|---|---:|
| full sample (25.1% a year on 24.5% volatility; worst drawdown −49%) | 1.02 (5.18) |
| early half (to 2013-03) / late half | 0.76 / 1.28 |
| eras 2002–08, 2009–15, 2016–19, 2020–22, 2023–25 | 1.08, 0.97, 1.81, 0.51, 1.55 |
| control: forward splits, same rule | 0.47 (2.39) |
| control: same events 60 sessions later / earlier | 0.45 / 0.63 |
| ratio under 1-for-5 / 1-for-5 to under 1-for-20 / 1-for-20 and over | 0.09 / 0.49 / 0.86 |
| names trading $5M a day or more (405 events) | 0.95 (4.79) |

- **Every era is positive**, and the liquid names are as strong as the rest.
- **These shares fall anyway.** The same short opened 60 sessions before or after the split
  earns 0.63 and 0.45. The split adds to a decline that is already there; it does not
  create one.
- **The forward-split control is not zero** (0.47): shorting any recently split share
  against IWM earned something in this sample, which I did not expect and have not explained.
- **WAIT is empty.** CRSP's declaration date is a median of one session before the ex-date,
  so only 114 events leave a session to trade: Sharpe 0.27 (t 1.37). The share falls 3.9%
  against IWM on X−1 (t −8.0) and 3.7% on X (t −6.4), but catching that needs the company's
  own announcement date, which CRSP does not carry.

## Checks that were not pre-specified (`checks.py`) [V]

| | |
|---|---:|
| alpha against IWM and SPY | 25.1% a year (t 5.17); betas −0.03 and 0.03 |
| per event, 20 sessions, short less IWM | mean +9.1%, median +7.8%, 64% positive (t 5.13 by month) |
| per event, 5th and 95th percentile; worst and best | −65% and +86%; −714% and +412% |
| without the ten best events / the ten worst | 0.80 / 1.42 |
| first five earning sessions / the other fifteen | 0.94 / 0.57 |
| less the mean of the two moved-window controls | 0.50 (t 2.53) |

- **The tail is the risk.** One event cost seven times its position: a small share that
  multiplied while short. A 10% position in that name loses 71% of the book. No fixed
  position size in the test protects against it.
- **The event's own part is about half.** After taking out what the same names earn in
  ordinary months, 0.50 is left, most of it in the first five sessions.

## Borrow, measured on the names the book would hold (`borrow_now.py`) [V, 2026-11-15]

Alpaca's feed lists 1,189 reverse splits with ex-dates in the last 365 days. The feed is
not limited to common shares: it includes closed-end funds and ETFs. Eligibility uses the
same two floors on Alpaca's raw daily bars; 314 rows had no ex-day bar or fewer than ten
bars and count as not eligible. Flags are today's.

| ex-date | set | events | listed today | shortable (all easy to borrow) |
|---|---|---:|---:|---:|
| 0–30 days ago (held now) | all | 92 | 73 | 6 |
| | eligible ($2, $500k) | 32 | 32 | **4** |
| | eligible and $5M a day | 8 | 8 | **0** |
| 31–90 days ago | eligible | 86 | 74 | 6 |
| | eligible and $5M a day | 34 | 29 | 2 |
| 91+ days ago | eligible | 365 | 314 | 34 |

- **Four of the 32 names the book would hold today can be shorted**, and one of the four
  (MMT) is a closed-end fund. None of the eight liquid ones can.
- **The October kill stands, now on the right set.** Conditioning on size and liquidity
  does not rescue the borrow: about one name in eight.
- **Not measured:** whether the few shortable names fall as the others do (the history
  holds no borrow flags), and what a hard-to-borrow locate would cost at another broker.

## What I conclude

1. The price pattern is real, large and persistent: about 9% in 20 sessions against IWM.
2. The desk cannot earn it as a short at Alpaca. A shadow book that shorts names the
   broker will not lend would report a return nobody can have, so none was built.
3. **A use that needs no borrow:** keep reverse-split names out of long books that buy
   recent losers (`st_reversal_wide` is the one on the list). A share within 21 sessions of
   a reverse split has lost a median 7.8% more than IWM. This is a filter to test inside
   that book, on that book's own universe; it is not tested here.
   **Counted afterwards, 2026-11-15:** only 152 reverse splits in 26 years fall inside the
   2,000-largest-stock panel that book draws on (about six a year, CRSP to 2025-12-31), so
   the filter would change almost nothing there. Dropped as a use for that book [V: a join
   of the two staged files, counts only].

## What would reopen it

- A broker with hard-to-borrow locates and a measured fee (the fee would have to sit well
  under 9% per 20 sessions, about 110% a year, which is possible but unmeasured).
- Listed puts on the liquid names: 405 events since 2000 traded $5M a day; whether they
  had options, and what the puts cost, is not measured.
- An announcement-date source (the 8-K) for the X−1 and X sessions, which hold 7.6% of the
  fall and are before any borrow squeeze.

**Not independently reviewed.** The staging, placement and alignment follow the
special-dividend scripts, which were (`results/ideas/2026-11-15_special_dividends.md`).
