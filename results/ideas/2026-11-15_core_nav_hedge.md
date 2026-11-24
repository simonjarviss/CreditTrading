# Idea card — Why the core paper book is flat, and whether an ETF hedge would fix it

**Slug:** `core_nav_hedge` · **Written:** 2026-11-15 ·
**Status:** SET ASIDE. The hedge does not help on 20 years of history. The live book is
flat because one part of it, which earns nothing on average, had a draw near its worst on
record; the signal's own part earned more than its average ·
**Reproducer:** `python3 results/ideas/core_nav_hedge/explore.py --data <data/cef>`, and
`QUANTT_ENV_FILE=<env> python3 results/ideas/core_nav_hedge/live_split.py <cef_universe.csv> <out.csv>` ·
**Panels:** the desk's CEF price and NAV panels, last rows **2026-10-14** (NAV) and
2026-10-15 (prices); MUB, HYG and BKLN adjusted closes from Yahoo (fetched 2026-11-15);
Alpaca's end-of-day equity and fills for the `cef` paper account to **2026-11-13**; Yahoo
closes and NAVs for the 13 funds (fetched 2026-11-15).

## The question

The team lead asked on 2026-11-15 for the deployed strategy to be made profitable. The
`cef` paper account stood at $99,902.79 on 2026-11-13 against $100,000 at the start: 34
sessions, −0.10%, 7.3% annualised volatility [V: Alpaca end-of-day equity].

## What the live record shows (`live_split.py`) [V, 2026-11-15]

Rebuilt from the account's fills. The rebuild sums to −$87 against Alpaca's −$97; the
difference is fees and Yahoo-versus-auction closes.

| 2026-09-29 to 11-13, USD | hold | NAV part | discount part | fills |
|---|---:|---:|---:|---:|
| whole book | +522 | −3,164 | +3,685 | −609 |
| muni funds (2) | −2,407 | −3,350 | +943 | −229 |
| multi-sector (8) | +2,126 | −633 | +2,758 | −276 |
| loan (1) | +671 | +636 | +35 | −65 |
| high yield (2) | +132 | +184 | −52 | −39 |
| to 10-12 | +1,477 | +226 | +1,251 | 0 |
| 10-13 to 10-30 | −2,144 | −2,582 | +438 | −309 |
| 11-02 to 11-13 | +1,189 | −807 | +1,996 | −300 |

- **The signal is earning.** The discount part is what the book trades on: a fund priced
  rich to its own history is sold, a cheap one bought. It made +$3,685, positive in all
  three periods and on both the long and the short side.
- **The loss is the funds' own asset values moving.** The book was short the two muni
  funds while their NAVs rose about 8% (XMQYX 10.72 on 10-07 to 11.78 on 11-06), then long
  them as NAVs fell in the last three sessions.
- **Fills cost −$609**, 6.5bp on $931,022 traded.

## What was fixed before the test (`explore.py`)

- **The book:** the frozen spec's targets and band, unchanged, shift(2).
- **The split:** NAV part = held weight × the fund's NAV return; discount part = the rest.
- **The hedge:** one ETF per fund group (muni → MUB; high yield and multi-sector → HYG;
  loan → BKLN). Each fund's beta is the slope of its 5-session NAV return on the ETF's, over
  the 252 sessions ending the day before. The hedge is minus weight × beta, on shift(2).
- **Variants:** every group; the muni group alone; every group but never short MUB (Alpaca
  did not lend the muni ETFs on 2026-10-15 and 10-18, `results/cef/NAVHEDGE_SCREEN_2026-11-02.md`).
- **Expected:** the NAV part earns nothing and adds volatility, so a hedge raises the
  Sharpe a little.
- **The live window is not in the test.** The panel ends before most of it.

## What it showed (gross, shift(2), no costs) [V]

The 13-fund book holds nothing before 2013, so every figure is 2013-01 to 2026-10-14.

| | return a year | volatility | Sharpe (t) | 2013–15 | 2016–19 | 2020–22 | 2023–26 |
|---|---:|---:|---:|---:|---:|---:|---:|
| book, as deployed | 5.69% | 5.71% | 1.00 (4.20) | 1.28 | 0.56 | 1.01 | 1.79 |
| its discount part | 5.90% | 5.77% | 1.02 (4.31) | 1.15 | 0.76 | 1.00 | 1.82 |
| its NAV part | −0.21% | 2.21% | −0.09 (−0.40) | 0.27 | −0.55 | −0.10 | 0.00 |
| hedged, every group | 5.30% | 5.73% | 0.93 (3.90) | 1.31 | 0.45 | 0.90 | 1.70 |
| hedged, muni only | 5.38% | 5.73% | 0.94 (3.96) | 1.28 | 0.56 | 1.02 | 1.52 |
| hedged, no MUB short | 5.37% | 5.72% | 0.94 (3.96) | 1.31 | 0.45 | 0.89 | 1.77 |

The return and volatility columns are from 2009, which is the same sample (flat until 2013)
at a different day count; the Sharpe ratios are unaffected.

- **The hedge lowers the Sharpe in every variant and does not lower volatility.** The
  expectation was wrong.
- **The NAV part is small and offsets the signal.** It is 15% of the book's variance and
  its correlation with the discount part is −0.22, so removing it removes a partial offset.
- **The ETFs explain little of it.** The hedge's own P&L explains 9.5% of the NAV part's
  variance and 0.9% of the book's, in line with the 1–7% the desk had on record.

## How unusual the live window is [V]

Every 34-session window in the backtest from 2013, at the spec's 1.3× sizing:

| 34 sessions, % of capital | backtest mean | 5th to 95th percentile | worst | live | windows below live |
|---|---:|---:|---:|---:|---:|
| NAV part | −0.03 | −1.80 to +1.78 | −3.52 | −3.16 | 0.4% |
| discount part | +1.34 | −2.60 to +6.73 | −7.71 | +3.69 | 82% |
| book | +1.31 | −2.51 to +6.87 | −7.75 | −0.10 | 30% |

- **The NAV loss is close to the worst 34 sessions in 13 years of backtest.** It is a rare
  draw from a part of the book that averages zero.
- **The book as a whole is at its 30th percentile:** an ordinary below-average stretch.
  The average window earns +1.3%, about $1,300 on this account.
- The live figures are in dollars of a $100,000 account and include fills; the backtest
  windows are gross. The comparison is approximate.

## What I conclude

1. The core book is doing what its history says. Nothing in the live record points to a
   broken signal.
2. An ETF hedge of the NAV exposure is not a fix. The 2026-11-02 closure stands, now on a
   measured return and not a power argument.
3. Seven weeks cannot make a 1.0-Sharpe book reliably profitable: its average 34 sessions
   earn 1.3% with a spread of 2.7%. More return sooner has to come from more independent
   books beside it, or from more size on this one, which is the team lead's decision.

## Not tested

- A cap on one group's net position. The book was 40–50% of capital net short the two
  muni funds in October before sizing (the group's 95th percentile since 2020 is 46%).
  The desk's earlier hard muni neutrality lowered the Sharpe from 0.97 to 0.82
  (`docs/RESEARCH_STATE.md`); a softer cap has not been read.
- Daily rather than 5-session betas, and Treasury ETFs as the hedge.

**Not independently reviewed.**
