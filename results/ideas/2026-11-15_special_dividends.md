# Idea card — special cash dividends: the wait for the ex-date pays, the days after it reverse

**Slugs:** `specdiv_wait`, `specdiv_after`, `specdiv_exday` · **Written:** 2026-11-15 ·
**Status:** `specdiv_wait` SHADOW book built, starting 2026-11-17 if its commit reaches the
`shadow` branch by then (see Next); `specdiv_after` EXPLORE, weak; `specdiv_exday` SET ASIDE ·
**Reproducer:** `python3 results/ideas/special_dividends/explore.py`, then
`python3 results/ideas/special_dividends/checks.py` and `checks.py --shifted` ·
**Panels:** CRSP distributions and daily rows on R2 (`scripts/research/stage_crsp_special_divs.py`),
special dividends with ex-dates 2000-01-04 to 2025-12-31, prices to **2025-12-31**; IWM and SPY
total returns from Yahoo (fetched 2026-11-10). CRSP rows are not in the repository.

## The idea

A company announces a one-off cash dividend, often several per cent of its price, one to
three weeks before the ex-date. Income buyers arrive before a large payment and leave once
they hold it. The team lead's event list (`docs/MISSION.md` §5, 2026-11-11) names special
dividends as an extension of the ex-date work. The desk counted these events in October
(`results/events/ssx/ssx_pm/HOW_WE_ADD_IT_2026-10-19.md`, family E1c: about 190 a year on
common stocks) and never read a return.

## What was fixed before the test

Only counts, yields and declaration leads had been read (3,626 events on common shares;
median yield 2.1%; median lead 13 calendar days).

- **The event:** CRSP distribution type `SD`, paid in US dollars, on a common share
  (`EQTY`/`COM`/`NS` on the ex-date), with a declaration date on CRSP. Funds are left out.
- **Dating:** CRSP gives a declaration date and no time. The news is taken as public by the
  close of the first session after it (D1). X is the ex-date.
- **Eligible, at the decision close:** price ≥ $2, 21-session dollar volume ≥ $500,000 (the
  closed-end fund test's values), yield (amount / that close) ≥ 1%.
- **Three books,** each name a fixed 10% of the book with IWM the same size the other way,
  scaled down when a side would pass 50% (the spin-off test's sizing):
  - **WAIT:** long. Decided at D1, filled at the next close, held to the close of X−1.
  - **EXDAY:** long for the ex-date only (CRSP's return includes the dividend).
  - **AFTER:** short over X+1, X+2 and X+3, the closed-end fund rule unchanged.
- **Expected signs, written first:** all three positive.
- **Controls:** the same books on every ordinary cash dividend of the same companies; the
  AFTER book moved ten sessions later.

## What it showed (gross, shift(2), no costs, no borrow) [V]

2000-06-01 to 2025-12-31 (IWM's history sets the start). 3,601 special dividends in the
window; 64 have no declaration date and are left out.

| book | events traded | gross Sharpe (t) | early / late half | 2023–25 | ordinary-dividend control | other control |
|---|---:|---:|---:|---:|---:|---:|
| WAIT | 1,654 (65 a year) | **1.10 (5.57)** | 0.78 / 1.36 | 0.64 | 0.59 | see the moved-window check |
| EXDAY | 1,716 | 0.56 (2.83) | 1.41 / −0.10 | −0.86 | 1.11 | — |
| AFTER | 1,743 | 0.63 (3.21) | 0.64 / 0.64 | −0.20 | 0.25 | ten sessions later: 0.06 |

- **WAIT** is positive in all five eras (0.67, 1.09, 1.76, 2.23, 0.64) and returns 6.6% a
  year on the book at 6.0% volatility, with about 2.5 names held. Its worst drawdown is 8.6%.
- **EXDAY is not a special-dividend effect.** The ordinary-dividend control is stronger
  (1.11), and the special version has been flat to negative since 2013.
- **AFTER** has the right sign in both halves and a dead placebo, but it is small and
  negative in 2023–25.
- **By yield (descriptive):** WAIT is 0.36, 0.39 and 1.18 for yields of 1–2%, 2–5% and 5%
  or more; AFTER is −0.14, 0.24 and 0.78. The effect is mostly in the large payments.
- **Event-time profile against IWM (eligible events):** the stock gains 16 to 43bp on each
  of the nine sessions before the ex-date, 23bp on the ex-date, then loses 25bp and 19bp on
  X+2 and X+3. Around the announcement it gains 72bp on the declaration date, 160bp on D1
  and 40bp on D1+1, none of which the WAIT book earns.
- The three books are uncorrelated with each other (−0.07 to 0.03).

## Checks, none pre-specified (`checks.py`, written after the first run) [V]

| check | WAIT | AFTER |
|---|---:|---:|
| alpha a year (t), with IWM and SPY as regressors | 6.9% (5.85) | 2.7% (3.10) |
| betas to IWM / SPY | −0.07 / 0.05 | 0.02 / −0.01 |
| mean per event against IWM (median; share positive) | +1.19% (0.64%; 57%) | +0.45% (0.30%; 54%) |
| without the ten best events | 0.98 | 0.40 |
| events with dollar volume ≥ $5M | 0.62 (t 3.15), 989 events | 0.30 (t 1.53) |
| events with dollar volume ≥ $20M | 0.49 (t 2.46), 556 events | 0.23 (t 1.16) |

- **Both parts of the wait pay:** the first three sessions held give 0.77 and the rest 0.84.
- **Moving the WAIT window:** the same names over the same number of sessions give 0.66,
  0.68 and 1.02 when the window is moved 60, 40 and 20 sessions EARLIER, and −0.14, 0.03 and
  −0.14 when moved 20, 40 and 60 sessions later. Companies announce a special dividend after
  a strong run. The earlier windows cannot be traded (the dividend is not yet announced), so
  WAIT may be the last leg of that run. It stops at the ex-date either way.
- **Dating:** CRSP's dates for Costco's five specials (for example declared 2023-12-14, ex
  2023-12-27) match what I recall of the company's announcements; I did not re-fetch a
  filing, so this is [U].

## What it does not show

- **Capacity.** Sharpe falls from 1.10 to 0.62 to 0.49 as the volume floor rises. A $1M
  book holds $100,000 a name, which the base filter supports. A $10M book holds $1M a name
  and needs the $20M floor to stay at 5% of a day's volume: plan on about 0.5, not 1.1.
- **Borrow** for AFTER, and dividend tax, are not modelled.
- **Live dating.** The test knows the declaration date. A live book knows only the day a
  feed first lists the dividend. Alpaca's feed marks specials and lists future ones (read
  2026-11-15: 73 special rows with pay dates after 2026-11-16, ex-dates out to 2027-02);
  how many days after the announcement a row appears is not measured, and the two sessions
  after the announcement are worth 0.77 of the result's Sharpe.
- **Type.** The live feed cannot reproduce CRSP's "common share" code exactly.
- CRSP lists only dividends that went ex; a special that was announced and cancelled is not
  in the sample. I did not count how often that happens.

## Next

- **Shadow book `specdiv_wait`** (`shadow/books/specdiv_wait.json`, `shadow/signals/specdiv.py`,
  `shadow/fetch/specdivs.py`), simulated, $1M, under the 2026-11-09 one-time approval. Long
  each eligible company 10% against IWM from the first session it is seen in Alpaca's feed
  to three sessions before the ex-date. Each row is stored with the day it was first seen,
  which measures the feed's lag. The live filter approximates CRSP's common-share code with
  the feed's `foreign` flag, the asset's exchange and its name.
- **First read of the real feed, 2026-11-15:** 67 special rows not marked foreign, 47 with a
  future ex-date; 22 companies pass the type filter with an ex-date at least three sessions
  ahead, and 12 of those yield 1% or more on the 2026-11-13 close (among them Costco at 2.7%
  and one at 88%, a liquidating payment). All 67 were already listed when the reader first
  ran, so none of them measures the lag.
- **Not running yet.** The commit is local: the team lead stopped pushes on 2026-11-15, and
  the VM follows the remote `shadow` branch. The start date in the book file must be moved
  if the push comes after 2026-11-17.
- AFTER waits for more evidence. EXDAY is closed.
