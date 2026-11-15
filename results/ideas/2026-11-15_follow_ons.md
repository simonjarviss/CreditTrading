# Idea card — Follow-on share offerings: the recovery after pricing was real and has faded

**Slug:** `follow_on_rebound`, `follow_on_drift` · **Written:** 2026-11-15 ·
**Status:** EXPLORE, not promoted. The pre-specified long is 0.71 gross over 2000–2025 and
0.26 since 2013; the short over the following forty sessions shows nothing ·
**Reproducer:** `python3 results/ideas/follow_ons/explore.py`, then `checks.py`, then
`checks.py --gap` ·
**Panels:** SDC new issues and CRSP daily rows on R2 (`scripts/research/stage_sdc_follow_ons.py`),
issue dates 2000-01-05 to 2025-12-31, prices to **2025-12-31**; IWM and SPY total returns
from Yahoo (fetched 2026-11-10). SDC and CRSP rows are not in the repository.

## The idea

A listed company sells new shares at a discount, and its share falls when the deal is
announced. If part of that fall is the pressure of placing the shares, it should come back
within days. The catalogue carried this as K6
(`results/events/SPECIAL_SITUATIONS_CATALOGUE_CORP_2026-10-15.md`): a published recovery
"within 7 sessions" for marketed deals, weaker for overnight deals, ranked low because most
deals are now overnight. No return was read. Its convertible-bond sibling E2 was measured in
October at +0.54% over days 2 to 5, fading to +0.17% in 2020–22
(`results/events/REPRO_CORP_EVENTS_2026-10-11.md`).

## What was fixed before the test

Only counts had been read: 13,491 US public follow-ons since 2000 matched to a CRSP common
share (about 500 a year); 8,044 launched before the issue date and 5,447 on it.

- **The event:** an SDC follow-on (not an IPO, US, public market), one per issuer and
  issue date D. SDC's issue date is the pricing date and can be the evening before the
  shares trade, so nothing is decided on D.
- **Eligible, at the close of D+1:** price ≥ $2 and 21-session dollar volume ≥ $500,000.
- **REBOUND:** long the share, short IWM the same size, 10% a name, scaled down when a side
  would pass 50%. Decided at D+1, filled at the close of D+2, earns D+3 to D+7.
- **DRIFT:** short, earns D+8 to D+47.
- **Controls:** REBOUND on the same events 30 sessions earlier and 30 later.
- **Named in advance as descriptive cuts:** by era, launched before the issue date
  ("marketed") against on it ("overnight"), offering size against market value, liquidity.

## What it showed (gross, shift(2), no costs) [V]

2000-06-01 to 2025-12-31; 10,409 eligible events (407 a year). REBOUND holds 8 names on
average and is at its 50% cap on 71% of sessions; no held name-day lacks a return.

| REBOUND (long D+3 to D+7) | gross Sharpe (t) |
|---|---:|
| full sample (8.5% a year on 12.0% volatility) | 0.71 (3.57) |
| early half (to 2013-03) / late half | 1.56 / 0.26 |
| eras 2002–08, 2009–15, 2016–19, 2020–22, 2023–25 | 1.34, 1.30, 0.17, 0.10, 0.15 |
| control: 30 sessions later | 0.04 |
| control: 30 sessions earlier | 1.88 |
| launched before the issue date / on it | 1.00 (5.1) / −0.30 (−1.5) |
| offering 13% of market value and over / under | 1.02 / 0.00 |
| names trading $5M a day / $20M a day | 0.15 / −0.18 |

| DRIFT (short D+8 to D+47) | gross Sharpe (t) |
|---|---:|
| full sample | 0.07 (0.34) |
| eras 2002–08, 2009–15, 2016–19, 2020–22, 2023–25 | −0.30, −0.15, −0.51, −0.16, 1.64 |

- **The dating caution was needed.** Deals launched on the issue date fall 2.9% against
  IWM on D+1 (t −18), not on D; deals launched earlier fall 2.5% on D (t −12).
- **The earlier-window control is not a placebo.** Companies sell shares after a rise:
  the share beats IWM on each of the ten sessions before D. 1.88 is that selection, which
  nobody could trade.
- **DRIFT is nothing.** Positive only in 2023–25, negative in the four eras before.
- **REBOUND lives in the small and illiquid end.** It is 0.15 on names trading $5M a day,
  which at this desk's size is most of what could be bought.

## Checks that were not pre-specified (`checks.py`) [V]

Written after the table above showed the rebound only where the launch came before pricing.

| REBOUND, launched before the issue date | all eras | 2000–07 | 2008–12 | 2013–17 | 2018–22 | 2023–25 |
|---|---:|---:|---:|---:|---:|---:|
| all 6,253 events | 1.00 | 2.09 | 1.56 | 1.02 | 0.46 | 1.00 |
| $5M a day (4,413) | 0.58 | 1.59 | 1.19 | 0.47 | −0.48 | 0.36 |
| 13% of market value and over (3,803) | 1.20 | 1.74 | 1.47 | 1.34 | 0.79 | 0.90 |
| per event, mean (median) | | +0.93% (+0.69%) | +0.70% (+0.55%) | +0.63% (+0.36%) | +0.27% (0.00%) | +2.77% (+0.03%) |
| launched on the issue date, per event mean | | −0.31% | 0.00% | −0.25% | −0.25% | −0.65% |

- **The typical event has stopped paying.** The median marketed event earned 0.69% in
  2000–07 and nothing since 2018. The 2023–25 Sharpe of 1.00 rests on a mean of 2.77%
  beside a median of 0.03%: a few large winners among 351 events.
- **Alpha against IWM and SPY** (marketed book): 14.4% a year (t 5.17), betas −0.05 and 0.03.
- **"Marketed" is the wrong word for a third of them** (`checks.py --gap`). Of the events
  launched before the issue date, 2,468 were launched one session before: announced one
  evening and priced the next day. Those earn 0.67 (t 3.37) and are positive in all five
  eras (0.41, 0.59, 1.11, 0.64, 0.68). Deals launched and priced on the same date earn
  −0.31 and are negative or flat in all five. I do not have an explanation for the
  difference, the cut was made after two earlier looks, and it is not evidence.

## What I conclude

1. The recovery after a follow-on was a real effect of about 0.7% in five sessions before
   2013 and has faded to about nothing for the typical deal.
2. The later short is not there in this sample.
3. Nothing here is promoted and no shadow book was built. A live book would also need a
   dated list of offerings with launch and pricing times, which the desk does not have
   (EDGAR 424B5 filings carry the pricing; the launch is a press release).

## What would reopen it

- The one-session-launch cut holding on offerings from 2026 on, collected from EDGAR with
  the rule fixed first.
- A reason, from the deal terms, why deals priced the same evening behave differently
  (registered directs and bought deals are candidates; SDC's type field was not read).

**Not independently reviewed.**
