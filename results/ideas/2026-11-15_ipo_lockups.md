# Idea card — IPO lock-up expiries: the fall is real but has moved earlier than the textbook window

**Slug:** `ipo_lockup_expiry` · **Written:** 2026-11-15 ·
**Status:** EXPLORE. The pre-specified book is weak since 2013 and is not promoted; an
earlier window found after looking still falls and needs unseen data ·
**Reproducer:** `python3 results/ideas/ipo_lockups/explore.py`, then
`python3 results/ideas/ipo_lockups/checks.py` ·
**Panels:** SDC new issues and CRSP daily rows on R2 (`scripts/research/stage_sdc_ipo_lockups.py`),
IPO dates 2000-01-24 to 2025-12-16, prices to **2025-12-31**; IWM total returns from Yahoo
(fetched 2026-11-10). SDC and CRSP rows are not in the repository.

## The idea

At an IPO the insiders agree not to sell for a fixed time, usually 180 days. The date is in
the prospectus, so the arrival of supply is known months ahead. The desk's catalogue listed
this as K5 (`results/events/SPECIAL_SITUATIONS_CATALOGUE_CORP_2026-10-15.md`, quoting about
−1.5% over three days) and dropped it on 2026-10-19 because 15 of 36 recent IPOs near day
180 were shortable at Alpaca (`results/events/SS_DESK_EXPANSION_2026-10-19.md`, row K5). No
return was read then. The mission brief asks for the gross result first.

## What was fixed before the test

Only counts had been read: 4,995 US IPOs on SDC since 2000 carry a lock-up date; 2,823 match
a CRSP common share that began trading within a week of the IPO date; 2,569 of those have a
180-day lock-up; median proceeds $114M.

- **The event:** SDC's lock-up expiry date (the earliest for a deal). L is the first
  session on or after it. SDC's date is the deal date plus the contract's days, so it is
  the prospectus date, not one learnt afterwards.
- **Eligible, at the close of L−3:** price ≥ $5 and 21-session dollar volume ≥ $1M (the
  spin-off test's floors for a new share).
- **The book:** short the stock over L−1, L and L+1, long IWM the same size; 10% a name,
  scaled down when a side would pass 50%.
- **Controls:** the same book 30 sessions earlier and 30 later.

## What it showed (gross, shift(2), no costs, no borrow) [V]

2000-06-01 to 2025-12-31; 1,670 eligible events (65 a year), no held name-day without a return.

| | gross Sharpe (t) |
|---|---:|
| full sample | 0.56 (2.82) |
| early half (to 2013-03) / late half | 1.29 / 0.19 |
| eras 2002–08, 2009–15, 2016–19, 2020–22, 2023–25 | 1.04, 0.85, −0.04, 0.37, −0.21 |
| window moved 30 sessions earlier / later | −0.00 / −0.16 |
| proceeds under $100M / $100M and over | 0.22 / 0.62 |
| 180-day lock-ups / other lengths (103 events) | 0.57 / −0.04 |

- **The dating is right.** Against IWM the stock loses 32bp on L−4, 24bp on L−2, 32bp on
  L−1 and 37bp on L, and nothing on L+1 or after; both moved windows are flat.
- **The pre-specified window has stopped working.** Per event, L−1 to L+1 averaged −1.40%
  in 2000–08 and −0.61% in 2009–15, then +0.09%, −0.18% and +0.33% in the three eras since.

## A check that was not pre-specified (`checks.py`) [V]

The profile put the fall on L−4 to L, so I summed each event's return less IWM over that
window. This was chosen after seeing the profile and is descriptive only.

| era | events | L−1 to L+1 | L−4 to L (t by month) |
|---|---:|---:|---:|
| 2000–2025 | 1,670 | −0.65% | −1.21% (−4.4) |
| 2000–2008 | 551 | −1.40% | −1.59% (−3.1) |
| 2009–2015 | 498 | −0.61% | −0.94% (−2.6) |
| 2016–2019 | 213 | +0.09% | −1.98% (−3.9) |
| 2020–2022 | 325 | −0.18% | −0.43% (+0.3) |
| 2023–2025 | 83 | +0.33% | −1.31% (−1.1) |

The selling appears to have moved a few sessions ahead of the expiry. The earlier window
was picked on this same sample, so its size is not evidence yet.

## What it does not show

- **Borrow.** The short is in shares listed about six months earlier. The October count
  (15 of 36 shortable) stands, and nothing here measures a borrow fee.
- **Which IPOs SDC dates.** About half of SDC's US IPO rows have no lock-up date and are
  not in the test.
- Early releases and extensions are not in SDC's field. Staggered second and third
  expiries of one deal are not tested.
- No book was run on the earlier window.

## Next

Only new data can test the earlier window: a shadow book that shorts L−4 to L on IPOs as
they reach day 180, which would also record whether each share is shortable that night.
It needs a free, dated list of recent IPOs with lock-up terms (EDGAR 424B4 prospectuses),
which the desk does not have yet.
