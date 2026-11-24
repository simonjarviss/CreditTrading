# Idea card — Newly converted savings banks: the first year is thrift beta, not an event

**Slug:** `thrift_conversions` · **Written:** 2026-11-15 ·
**Status:** SET ASIDE. Against seasoned savings institutions the first-year book is 0.32
(t 1.79), carried by 2002–08 and negative since 2016 ·
**Reproducer:** `QUANTT_ENV_FILE=<env> python3 scripts/research/stage_crsp_thrift_listings.py`,
then `python3 results/ideas/thrift_conversions/explore.py` ·
**Panels:** CRSP daily rows on R2, first listings 1995-02-14 to 2025-05-02, prices to
**2025-12-31**; IWM total returns from Yahoo (fetched 2026-11-10). CRSP rows are not in the
repository.

## The idea

A mutual savings bank that converts sells shares to its depositors at $10 and keeps its
old capital too, so it lists below tangible book value. Federal rules bar buybacks for a
year and a takeover for three (12 CFR 239.63). Friesen and Swift (2009), on a sample
before 2009, report positive excess returns for twelve months after the first-day jump
and a correction over the next eighteen. The niche hunt of 2026-11-15 ranked it first
(`results/ideas/2026-11-15_niche_hunt.md`). A few list each year and they are far too
small for a fund.

## What was fixed before the test

Only counts had been read: 169 new listings with SIC 6035/6036 since 1995, 147 with a
first close of $8 to $16.

- **Event:** a US common share whose first CRSP row is a savings institution with a first
  close of $8 to $16.
- **YEAR1:** decided at the close of day 4, filled at the close of day 5, earns days 6 to
  250. 10% a name, scaled down above ten names.
- **Two hedges, side by side:** IWM (tradable, from 2000-05), and the equal-weighted return
  of seasoned savings institutions (listed over three years; a median of 72 names; not
  tradable, but it says whether the result is about conversions or about small thrifts).
- **Control, LATER:** the same names on days 251 to 630, which the paper says is weak.
- **Expected:** YEAR1 positive against both hedges; LATER zero or negative.

## What it showed (gross, no costs) [V]

147 events: 51 in 1995–2001, 60 in 2002–08, 19 in 2009–15, 17 in 2016–25. About 4.8 names
held, 45% of the book invested on average.

| | Sharpe (t) | halves | 1995–2001 | 2002–08 | 2009–15 | 2016–25 |
|---|---:|---:|---:|---:|---:|---:|
| YEAR1 less seasoned thrifts | 0.32 (1.79) | 0.56 / −0.08 | 0.21 | 0.94 | 0.09 | −0.29 |
| YEAR1 less IWM (from 2000-05) | 0.36 (1.81) | 0.56 / −0.09 | 1.61 | 0.47 | 0.26 | −0.18 |
| YEAR1 with no hedge | 1.10 (6.13) | | | | | |
| LATER less seasoned thrifts | −0.12 (−0.65) | −0.06 / −0.27 | −0.44 | 0.63 | −0.39 | −0.35 |
| LATER less IWM | 0.13 (0.66) | 0.24 / −0.11 | 0.92 | 0.32 | −0.13 | −0.19 |

| per event | n | mean | median | positive | t |
|---|---:|---:|---:|---:|---:|
| days 2–5, raw | 147 | +0.1% | 0.0% | 48% | 0.27 |
| days 6–250, raw | 147 | +19.7% | +16.7% | 78% | 6.23 |
| days 6–250 less seasoned thrifts | 147 | +3.0% | −1.9% | 45% | 1.13 |
| days 6–250 less IWM | 107 | +8.7% | +3.6% | 56% | 2.66 |
| days 251–630 less seasoned thrifts | 145 | −8.2% | −7.0% | 37% | −3.27 |
| days 6–250 less seasoned thrifts, listed 2016–25 | 17 | −6.9% | −9.1% | 24% | −1.89 |

- **The first-year gain is what small thrifts earned anyway.** Unhedged the book looks
  strong (1.10); against other thrifts the median conversion lost 1.9%.
- **One era carries it.** Listings of 2002–08 beat seasoned thrifts by 9.9% (t 2.30). The
  36 listed since 2009 did not, and the 17 since 2016 trailed by 6.9%.
- **The published weak second and third year is there** (−8.2%, t −3.27 against seasoned
  thrifts), but it would be a short in shares of this size, hedged with a basket that
  cannot be traded.
- **Size:** median dollar volume on days 6 to 60 is $165,038 a day (quartiles $63,068 and
  $429,962); the median closing spread on day 5 is 0.60%.
- 2 of the held name-days in YEAR1 had no CRSP return and count as zero.

## What I conclude

1. As a first-year long this is not an event trade. It is thrift exposure, and since 2009
   there are three listings a year and no excess.
2. The second-step conversions the hunt wanted split out could not be told apart: CRSP
   showed no earlier listing of the same company for any of the 169.

## What would reopen it

- A list of conversions with their type and pro-forma price to tangible book (the
  prospectus has both), to test the cheapest ones alone.
- The dated steps after listing (stock plan at six months, buyback at twelve) as events in
  their own right.

**Not independently reviewed.**
