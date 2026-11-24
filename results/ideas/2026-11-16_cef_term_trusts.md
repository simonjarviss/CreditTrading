# Idea card — Term closed-end funds in their last year: a cash return, nothing over a short Treasury fund

**Slug:** `cef_term_trusts` · **Started:** 2026-11-16, **interrupted** (editor force quit about
20 minutes in) and **completed 2026-11-18** ·
**Status:** SET ASIDE. Buying a dated term fund at the end of the year before its scheduled
year earns +2.9% per event unhedged (38 events in 31 years), which is +0.05% over a short
Treasury ETF (t 0.03) and +0.6% over a matched bond ETF once events that share a December
are counted once (t 0.4; negative without the 2008 cohort). The version the idea really
needs, entry at a discount of 3% or more, could not be tested: no NAV history exists on
this desk or on Yahoo for any term fund that has terminated ·
**Reproducer:** `QUANTT_ENV_FILE=<env> python3 results/ideas/cef_term_trusts/stage.py`,
`python3 results/ideas/cef_term_trusts/explore.py --list`, `stage.py --yahoo`, then
`explore.py` and `checks.py` ·
**Panels:** every CRSP closed-end fund (1,295, dead included) on R2, daily, 1990-01-02 to
**2025-12-31**; CRSP name history and delisting rows to 2025-12-31; Yahoo ETF total returns
(MUB, HYG, AGG, SHY, PCEF) and X-symbol NAVs fetched 2026-11-18, used to 2025-12-31; the
desk's NAV panels, read only. Licensed rows are under `~/quantt_research/cef_term_trusts/`.

## What survived the interruption, and what was done about it

Nothing of the first researcher's code survived: no `explore.py`, no rule, no card. On disk
were three small staged tables (names, delistings, date spans, on the 2000 panel) and a
zero-byte `crsp_cef_daily_1990.parquet`. So **the rule below was written on 2026-11-18**,
after reading names, counts, delisting codes and liquidity, and before any return. The
staging script was rewritten and all four files rebuilt from 1990 (the copy now writes to a
temporary name and renames, so a kill cannot leave a short parquet). One change was made to
the rule after `--list` and before any return: a two-digit number counts as a year only
beside a term word, because "DOW 30" funds were being read as 2030.

## The idea

A term fund's prospectus names a date on which it liquidates at net asset value. A fund at
a discount must close it by then, with no forecast needed, and the funds are far too small
for a large investor. The desk's census of 2026-10-15 had already found term funds within
about 1% of NAV before termination is announced
(`results/events/CEF_CORP_ACTION_CENSUS_2026-10-15.md`), on 14 groups; no return over the
last year had been read with dead funds included.

## What was fixed before the test

- **Term fund:** a CRSP closed-end fund whose issuer name in force on the day matches a
  term word (TERM, TM, TRM, TT, TGT, TARGET, WDGT, MATURITY, DEFINED OPP and so on) or
  carries a year; LONG TERM, SH TM, LTD TRM and vintage years excluded. The scheduled year
  Y is the year in the name. Point in time: only the name row in force is read.
- **T250 (headline):** at the last session of year Y−1, buy every fund whose name carries Y,
  price ≥ $2 and 21-session dollar volume ≥ $100,000. Fill at the next close, earn from the
  session after (shift(2), `harness.evaluate`). Hold to the fund's last CRSP row (delisting
  return included) or the last session of Y. Equal weights, long only. **T120, T60:** the
  same from the end of June and of September of Y. The same on $500,000 a day beside it.
- **Hedges:** the equal-weighted return of all eligible CEFs that were never term funds; a
  matched bond ETF by name (MUB / HYG / AGG), events before the ETF existed left out and
  counted.
- **Control:** never-term funds of the same sponsor (first word of the name) and the same
  muni / not-muni category, over the same sessions.
- **Hindsight table:** every term fund, last 250 / 120 / 60 sessions before its actual last
  row, with a placebo window of equal length just before. Dated with hindsight; descriptive.
- **Expected (written first):** roughly a short bond fund's return unhedged, under 1% over
  the ETF and the control and not distinguishable from zero. The idea survives only with a
  per-event excess over both that is positive with t above 2 and larger than the spread.

## The list and the risk of the trade [V]

90 term funds by the rule, 1990–2025. 61 liquidated, 7 merged, 3 left by exchange or other
delisting, 2 dropped the term name and later merged, 2 dropped it and still trade as
perpetual funds, 15 trade today under a term name. So of 75 funds no longer term funds,
**14 (19%) did not end in a liquidation**. Of the 58 with a year in the name, 44 had their
last row in that year, 3 one year early and 3 two to four years early (the last six by
merger or early liquidation); names of 3 live funds gained or changed a year while listed.
CRSP names do not show an extension that leaves the name alone, so the 19% is a floor [U].

## What it showed (gross, shift(2), no costs) [V]

T250: 38 events, 1.2 a year (no eligible event with a scheduled year from 2009 to 2017), 2.2 funds held when
invested, invested 47% of sessions, turnover 1.3 a year, median hold 228 sessions. 2 funds
were already gone at the decision close and 14 failed the price or volume filter.

| T250, calendar book | Sharpe (t) | return / vol a year | halves | 2002–08 | 2009–15 | 2016–19 | 2020–22 | 2023–25 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| long only | 0.60 (3.33) | 2.0% / 3.4% | 0.98 / 0.26 | 1.28 | none | 1.31 | −0.20 | 1.10 |
| less the CEF market | 0.06 (0.31) | 0.5% / 9.4% | 0.26 / −0.19 | 0.39 | none | −0.30 | −0.21 | −0.51 |
| less matched ETF (25 events) | 0.03 (0.19) | 0.1% / 3.8% | 0.21 / −0.05 | 0.31 | none | −0.53 | 0.06 | 0.02 |
| term less control (34 events) | 0.13 (0.72) | 1.4% / 10.6% | 0.29 / −0.15 | 0.54 | none | −0.25 | −0.17 | −0.28 |
| control less the CEF market | −0.10 (−0.55) | −0.8% / 8.3% | −0.10 / −0.16 | −0.26 | none | −0.12 | −0.17 | −0.42 |

Returns are per year of calendar time, idle sessions included. Split date 2010-06-29.

| buy and hold, per event | n | mean | median | share positive | t (clustered by entry month) |
|---|---:|---:|---:|---:|---:|
| T250 fund return | 38 | +2.94% | +3.14% | 87% | 1.88 |
| less the CEF market | 38 | +4.88% | +3.26% | 63% | 1.05 |
| less matched ETF | 25 | +1.83% | +1.79% | 72% | 1.49 |
| less control | 34 | +6.54% | +6.50% | 62% | 1.55 |
| T120 fund / less ETF / less control | 31 / 20 / 27 | +2.22% / +0.86% / +8.28% | +2.06% / +0.94% / +3.67% | 97% / 65% / 70% | 5.12 / 0.81 / 1.53 |
| T60 fund / less ETF / less control | 31 / 21 / 27 | +1.32% / +0.97% / +4.94% | +1.09% / +0.85% / +1.95% | 100% / 67% / 63% | 5.83 / 1.41 / 1.37 |
| T250 on $500k a day: fund / less ETF / less control | 18 / 13 / 17 | +1.51% / +0.52% / +3.72% | +2.42% / +1.18% / +2.65% | 78% / 62% / 53% | 1.10 / 0.24 / 0.74 |

Held funds: median dollar volume $280,568 a day, median price $9.87, median closing spread
20bp (90th percentile 189bp), 26bp on the decision day.

Hindsight table, 61 liquidated funds (window placed on the actual last row): last 250
sessions fund +4.6% (t 5.7), less the CEF market +0.3% (t 0.1), less ETF +1.3% (t 1.1, n 36),
less control +2.9% (t 0.8, n 48); placebo window less the market −3.5% (t −1.8). Last 60
sessions: fund +1.3%, 93% positive; less ETF +1.4% (t 1.9); less control +4.3% (t 1.7).

The bar set in advance (t above 2 against both the ETF and the control) is not met by any
book.

## Checks that were not pre-specified (`checks.py`) [V]

| | |
|---|---|
| T250 per event less SHY (27 events from 2002) | +0.05%, median +0.48%, t 0.03 |
| the same after half the fill-day spread (median 14bp, mean 24bp) | −0.08%, t −0.06 |
| less matched ETF, one figure per decision year (9 cohorts) | +0.57%, t 0.37; **−0.27% without the 2008 cohort** |
| less control, one figure per decision year (17 cohorts) | +2.8%, t 0.87; +0.6% without 2008 |
| by kind: government and investment grade (17) / muni (9) / credit (12), fund return | +5.3% / +2.3% / **+0.1%** (58% positive) |
| scheduled year 2022 (4 events) | −8.8%; the one fund that did not terminate lost 22% |
| worst drawdown inside a hold | median −1.5%, worst −27.7% |
| share of the return arriving in the last five sessions | 0.1% of 2.9%; no last-day move above 1% |
| less PCEF (20 events from 2010) | +1.0%, median 0.0%, t 0.33 |

The per-event excess over the ETF (+1.8%) and the calendar book (0.1% a year) differ
because four insured muni trusts entered together in December 2007 and beat MUB by 7.3% in
2008; they are four events but one book-year. The stale-close and final-payment artifact
was tested and is absent: the return accrues evenly and nothing arrives on the last row.
The ex-date drift is not relevant to a hold of 228 sessions in total returns.

## With NAV: not testable on past terminations

Yahoo served a NAV for 7 of 46 term-fund tickers asked (all live funds; every terminated
fund returned nothing, and so did live ETX and FTHY on two attempts). The desk's panels add
7 more, all live. **No T250 event has a NAV**, so the discount path into termination and the
return from buying at 3% or more below NAV were not measured. No weaker test was put in its
place.

## The live book (CRSP to 2025-12-31; discounts from Yahoo and desk NAVs at that date) [V]

| fund | year in name | price | $M a day | spread, bp | price to NAV |
|---|---:|---:|---:|---:|---:|
| BGB | 2027 | 11.78 | 1.67 | 17 | −5.3% |
| BSL | 2027 | 13.50 | 0.74 | 14 | −4.5% |
| FTHY | 2027 | 14.07 | 2.48 | 14 | no NAV served |
| ETX | 2028 | 18.70 | 0.52 | 47 | no NAV served |
| DTF | 2028 | 11.42 | 0.09 | 53 | −5.8% |
| BTT | 2030 | 22.82 | 3.21 | 18 | −7.3% |
| BMN | 2037 | 26.18 | 0.33 | 59 | +1.6% |
| BCAT, ECAT, BSTZ, BMEZ, BTX, MEGI, FINS, JLS | none in name | | 0.4 to 9.6 | 7 to 51 | −5.4% to −16.3% |

The eight without a year have termination dates in their prospectuses that were not
fetched [U]. The prices are six weeks older than this note.

## What I conclude

Without a discount at entry a term fund in its last year is a cash-like holding, and that is
what the data show: the return equals a short Treasury fund's, the credit funds earned
nothing, and the 2022 cohort shows the two real risks (a portfolio that is not yet cash when
rates and spreads move, and a fund that converts instead of terminating). The pull to NAV
is real only when there is a gap to pull, and the census and this test agree that by the
last year the gap has usually closed. It fails the bar set in advance. Not a shadow book as
specified. It is set aside, not killed, because the conditional trade was never tested.

A live feed would be easy if the trade existed: the name and the prospectus fix the date
years ahead, and NAV is published daily. Capacity is $100k to $1M at best ($280,000 a day
median volume).

## What would reopen it

1. A NAV history for terminated term funds (N-CSR and N-PORT period-end NAVs through
   `edgar_client`, or a CEFConnect archive), to test entry at a discount of 3% or more two
   to three years out, where today's 2027–2030 funds stand at 4% to 7% below NAV. That is a
   different, longer trade than the one tested here, and it carries the conversion risk
   counted above (at least 19%).
2. Prospectus termination dates and extension votes read from EDGAR for all 90 funds, so
   that the entry date and the extension count stop depending on the name.
3. A paper watch of the seven dated live funds needs no approval to record: price to NAV
   each month to their dates.

## Could not do

NAV-conditional test (no NAV for any dead term fund); exact prospectus dates and
extensions that left the name unchanged (EDGAR not read); ETF-hedged figures before 2003
(no bond ETF existed: 13 of 38 events have none); borrow was not needed (long only).
