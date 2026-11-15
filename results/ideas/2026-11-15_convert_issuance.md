# Idea card — Buying the issuer after a convertible issue: small, steady, and in liquid names

**Slug:** `convert_rebound` · **Written:** 2026-11-15 ·
**Status:** EXPLORE. Positive in every era and on liquid names, but small: 0.67 gross as
fixed, 0.42 to 0.56 under the checks. Not on shadow: there is no live list of issues yet ·
**Reproducer:** `python3 results/ideas/convert_issuance/explore.py`, then `checks.py`; the
headline look is `news_dating.py --year Y` for each year, then `headline_dated.py` ·
**Panels:** SDC new issues and CRSP daily rows on R2 (`scripts/research/stage_sdc_convertibles.py`),
issue dates 2000-01-13 to 2025-12-23, prices to **2025-12-31**; IWM and SPY total returns
from Yahoo (fetched 2026-11-10). SDC and CRSP rows are not in the repository.

## The idea

Funds that buy a new convertible and hedge it sell the issuer's share short as the deal
prices. That selling is not a view on the company, so the share should recover over the
next few sessions. The desk measured this once as E2
(`results/events/REPRO_CORP_EVENTS_2026-10-11.md`): +0.54% over days 2 to 5 on 755 events of
2011–22 dated from TRACE, fading to +0.17% in 2020–22. SDC dates issues from 2000 to 2025,
so the years before 2011 and after 2022 are new.

## What was fixed before the test

Only counts had been read: 3,337 SDC convertible issues matched to a CRSP common share
(about 130 a year), 1,403 in a public market.

- **The rule is the follow-on test's, imported unchanged**
  (`results/ideas/follow_ons/explore.py`): D is SDC's issue date; decided at the close of
  D+1 with price ≥ $2 and 21-session dollar volume ≥ $500,000; long 10% a name against IWM,
  scaled down above 50%; filled at the close of D+2; earns D+3 to D+7.
- **Controls:** the same events 30 sessions earlier and 30 later.

## What it showed (gross, shift(2), no costs) [V]

2000-06-01 to 2025-12-31; 2,840 eligible events (111 a year); invested on 76% of sessions,
2.2 names held on average; 5 of 14,172 held name-days had no return.

| | gross Sharpe (t) |
|---|---:|
| full sample (4.6% a year on 6.9% volatility) | 0.67 (3.39) |
| early half (to 2013-03) / late half | 0.77 / 0.59 |
| eras 2002–08, 2009–15, 2016–19, 2020–22, 2023–25 | 0.81, 0.24, 1.04, 0.36, 0.62 |
| control: 30 sessions later | −0.10 |
| control: 30 sessions earlier | 0.94 |
| issued 2011–22 (the years E2 saw) / outside them | 0.33 / 0.59 (t 3.0) |
| public market / private and 144A | 0.30 / 0.63 |
| names trading $5M a day / $20M a day | 0.68 (3.4) / 0.49 (2.5) |

- **The fall and the recovery are both in the profile.** Against IWM the share loses 0.55%
  on D−1, 2.54% on D and 0.56% on D+1, then gains 0.20% on D+2 and 0.14%, 0.02%, 0.14%,
  0.09% and 0.04% over the five sessions the book holds.
- **It holds in liquid names**, unlike the follow-on rebound: 2,549 of 2,840 events trade
  $5M a day.
- **The earlier-window control is selection.** Companies issue after their shares rise.
- **The years E2 had not seen are the stronger ones** (0.59 against 0.33).

## Checks that were not pre-specified (`checks.py`) [V]

| | |
|---|---:|
| alpha against IWM and SPY | 4.5% a year (t 3.30); betas −0.04 and 0.06 |
| per event, D+3 to D+7 less IWM | mean +0.44%, median +0.26%, 53% positive (t 3.0 by month) |
| per event mean by era | +0.51%, +0.16%, +0.54%, +0.28%, +0.72% |
| without the ten best events | 0.42 (t 2.13) |
| the same hold begun one / two sessions later | 0.45 (t 2.30) / 0.56 (t 2.83) |
| begun one session earlier (D+2, which the book cannot reach) | 0.87 (t 4.38) |

- **The effect is small per event** (0.26% for the median one) and a fifth of the Sharpe
  comes from ten events.
- **It decays by the day.** Starting at D+2 is worth 0.87, D+3 0.67, D+4 0.45. A live book
  that learns of the pricing the same evening and fills at the next close would be on the
  D+2 row; one that reads a list a day late would be on the D+4 row.

## A second look with headline dates (`news_dating.py`, `headline_dated.py`) [V, read 2026-11-15]

Run after the tables above, on the same events: a re-dating, not a new sample.

- **Alpaca's news feed names most recent deals.** For each SDC issue of 2015–2025 I read
  the issuer's headlines from seven days before to three after the issue date. A headline
  with "convertible" exists for 430 of 1,286: 8% to 30% a year through 2022, 46% in 2023,
  69% in 2024 and 73% in 2025 (87% of 2025's 144A deals). In 2025, 118 of 119 first
  headlines came outside trading hours (after 16:00 or before the open).
- **SDC's date is the reaction session about half the time.** Taking S0 as the first
  session that opens after the headline, S0 equals SDC's date for 218 events, is the
  session after it for 110 and the session before it for 64.
- **Dated from the headline, the result is not there in this sample:**

  | 2015–2025, 392 events | gross Sharpe (t) | 2015–22 | 2023–25 | per event mean (median) |
  |---|---:|---:|---:|---:|
  | decided at the close of S0, earns S0+2 to S0+6 | 0.29 (0.96) | −0.30 | 1.02 | +0.61% (+0.12%) |
  | filled at the close of S0, earns S0+1 to S0+5 | 0.20 (0.67) | −0.37 | 1.01 | +0.43% (+0.07%) |

  The events with a headline are a third of the list and not a random third (159 of them
  before 2023), so this is weak evidence either way. It does not confirm the SDC-dated
  result, and better dates did not make it larger.

## What it does not show

- **SDC's issue date is not checked against filings.** The special-dividend check
  (`results/ideas/2026-11-15_special_dividends.md`) found CRSP's dates up to four days
  early. Here the profile puts the fall on D, so the date is at least close.
- **Costs.** 0.26% a median event is the same size as a round trip in a mid-cap at the
  close; the desk does not model costs in research, and this is the result where they
  would matter most.

## Next

- A live list exists in principle: Alpaca's news feed, from 2024 on, with the launch timed
  to the minute. A reader would have to tell a new offering from a repurchase or a price
  move ("Plunges after convertible offering"), which the one-word match here does not.
- Not promoted. The SDC-dated result is small and the headline-dated one does not confirm
  it. A shadow book would be a way to collect clean events, not a bet on 0.67.

**Not independently reviewed.**
