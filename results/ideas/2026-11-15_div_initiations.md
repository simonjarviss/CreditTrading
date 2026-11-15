# Idea card — Dividend initiations and resumptions: no drift left to buy after the news

**Slug:** `div_initiation_drift` · **Written:** 2026-11-15 ·
**Status:** SET ASIDE. The pre-specified long earns 0.31 gross, no more than the same shares
earn six months later ·
**Reproducer:** `python3 results/ideas/div_initiations/explore.py` ·
**Panels:** CRSP distributions and daily rows on R2
(`scripts/research/stage_crsp_div_initiations.py`), ex-dates 2000-01-27 to 2025-12-30, prices
to **2025-12-31**; IWM total returns from Yahoo (fetched 2026-11-10). CRSP rows are not in
the repository.

## The idea

A company that has paid nothing for two years and declares a dividend is saying its cash
flow will last. The published record is a drift of several percent over the following year.
It is a long in ordinary shares, slow enough that the entry day should not matter.

## What was fixed before the test

Only counts had been read: 1,625 events since 2000 (about 63 a year, 169 of them in 2003);
1,006 first-ever dividends and 619 resumptions; 30 with no declaration date.

- **The event:** an ordinary cash dividend on a common share with no cash dividend in the
  730 days before its ex-date, the share on CRSP for at least those 730 days.
- **Dating:** D1 is the first session after CRSP's declaration date. The decision is one
  session later, at D1+1, because the special-dividend check found CRSP's date ahead of the
  filing for half its sample (`results/ideas/2026-11-15_special_dividends.md`).
- **Eligible, at the close of D1+1:** price ≥ $2 and 21-session dollar volume ≥ $500,000.
- **The book:** long the share, short IWM the same size, 10% a name, scaled down when a
  side would pass 50%; earns D1+3 to D1+62.
- **Controls:** the same events 120 sessions later, and 60 sessions earlier.

## What it showed (gross, shift(2), no costs) [V]

2000-06-01 to 2025-12-31; 1,123 eligible events (44 a year), 10 names held on average. 295
of 67,129 held name-days had no CRSP return and count as zero.

| | gross Sharpe (t) |
|---|---:|
| full sample (2.2% a year on 7.0% volatility) | 0.31 (1.57) |
| early half (to 2013-03) / late half | 0.54 / 0.08 |
| eras 2002–08, 2009–15, 2016–19, 2020–22, 2023–25 | 0.49, 0.34, −0.19, 0.77, −0.31 |
| control: same events 120 sessions later | 0.36 (1.82) |
| control: same events 60 sessions earlier | 1.45 (7.34) |
| first-ever dividends / resumptions | 0.22 / 0.48 |
| names trading $5M a day / $20M a day | 0.16 / 0.14 |
| first 20 earning sessions / the other 40 | 0.46 / 0.22 |

- **The control is as good as the book.** The same shares held four months later earn
  0.36. Whatever these companies earn against IWM, the declaration does not add to it.
- **The move is before and at the news.** Per event against IWM: +0.64% and +1.34% in the
  two ten-session blocks before D1, +1.66% in the block that starts on D1 (most of it not
  earned by a book that fills at the close of D1+2), then 0.2% to 0.4% a block with no t
  above 1.6.
- **Nothing since 2013.** Late half 0.08.

## What would reopen it

- A feed that gives the declaration within minutes, to test the first sessions after the
  news; CRSP's date cannot place them (the +1.66% block contains the announcement itself).
- Resumptions alone (0.48, t 2.4, 396 events) are the better half, seen after the fact.

**Not independently reviewed.**
