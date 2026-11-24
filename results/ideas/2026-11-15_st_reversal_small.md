# Idea card — Short-term reversal in smaller stocks: stronger than in large ones, and all on the short side

**Slug:** `st_reversal_small` · **Written:** 2026-11-15 ·
**Status:** EXPLORE. The long-short book beats the large-stock one (1.18 against 0.96), but
the half that needs no borrow has earned nothing since 2013. Not promoted ·
**Reproducer:** `python3 scripts/research/stage_crsp_equities.py --top 4500`, then
`python3 results/ideas/st_reversal_small/explore.py` ·
**Panel:** CRSP daily on R2, the 4,500 largest US common stocks each month with delisted
names included, last date **2025-12-31**; IWM total returns from Yahoo (fetched 2026-11-10).

## The idea

`st_reversal_wide` (`results/ideas/2026-11-10_st_reversal_wide.md`) is paid for providing
liquidity: buy the week's losers, sell its winners, within each industry. On the 1,500
largest stocks it is 0.96 gross and 0.67 since 2013. Below the top 1,500 liquidity is
scarcer and large funds cannot operate, so a small book should be paid more.

## What was fixed before the test

Nothing on this panel had been read. The rule is the wide book's, imported unchanged. The
only change is the universe: market-value rank 1,501 to 4,000, price ≥ $5, and 21-session
dollar volume ≥ $500,000. Three books from the same weights: both sides; the long side
alone against IWM (no borrow needed); the short side alone against IWM.

## What it showed (gross, shift(2), no costs, no borrow) [V]

About 1,125 names a day; turnover 164 times a year. 4,528 held name-days had no row (a
stock that stopped trading) and count as zero.

| | both sides | long leg vs IWM | short leg vs IWM |
|---|---:|---:|---:|
| full sample, Sharpe (t) | 1.18 (6.00) | 0.52 (2.63) | 0.90 (4.56) |
| early half / late half | 2.09 / 0.93 | 1.13 / −0.02 | 1.05 / 0.99 |
| 2002–08 | 1.77 | 1.09 | 1.08 |
| 2009–15 | 0.38 | 0.63 | 0.09 |
| 2016–19 | 1.12 | 0.24 | 1.05 |
| 2020–22 | 2.06 | 0.65 | 1.94 |
| 2023–25 | 0.64 | −1.26 | 0.99 |
| control: signal 21 sessions stale | 0.30 | −0.26 | 0.49 |
| return a year / volatility | 15.3% / 13.0% | 6.2% / 11.9% | 22.0% / 24.5% |

- **Rank 1,501–2,500 gives 1.19 and 2,501–4,000 gives 1.24**; from 2013 they are 0.94 and 1.13.
- **Since 2013 the money is in selling the week's winners.** Small stocks that jumped fall
  back; small stocks that fell have not come back. The long leg lost 17% a year against IWM
  in 2023–25.
- **Capacity is not the limit.** At $1M the median position is 0.01% of the name's daily
  volume and the 95th percentile 0.14%.

## What I conclude

1. Liquidity provision does pay more in smaller stocks: 1.18 against 0.96, and 0.93 against
   0.67 since 2013.
2. The part a small account can run without borrow (the long leg) does not work now.
3. The short leg needs borrow in small stocks that have just jumped, which are the names
   Alpaca most often will not lend (the reverse-split read of the same day found 4 of 32
   shortable, `results/ideas/2026-11-15_reverse_splits.md`). Borrow on this book's own
   shorts is not measured.

## What would reopen it

- A daily read of Alpaca's shortable flag on the book's own short candidates. If most are
  shortable (these are larger than reverse-split names), the both-sides book is worth a
  shadow run once a live small-stock price panel exists.
- 164 turns a year: this is the idea where trading costs decide, and the desk has no
  measurement of them in small stocks.

**Not independently reviewed.**
