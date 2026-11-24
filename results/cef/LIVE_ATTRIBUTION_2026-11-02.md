# Live P&L attribution, cef paper account, 2026-09-29..10-30 (2026-11-02)

Research output: zero trials, no counter moved, nothing on the live path.
Tool: `scripts/cef/live_attribution.py` (fetch, then analyse); this branch,
commits b6c882b, 2cc37d2, 25591d1. Aggregates only: the per-session equity,
per-name and position tables stay outside this public repository (the tool
refuses to write them where git can see them) until the team lead rules.

**Provenance.** Every figure is [V]. The main session ran a live read-only
`fetch` with keys on 2026-11-02, and analyse rebuilt the book from Alpaca's
FILL activities. Inputs:
- SIP daily closes (raw).
- yfinance NAVs (`X{tk}X`).
- Distributions from two sources, as in `quantt/session/dist_score.py`:
  Alpaca corporate actions and yfinance dividends.

The official P&L is Alpaca's EOD portfolio history (SYSTEM.md §5,
2026-10-19).

## Reconciliation

| | USD |
|---|---:|
| official: EOD equity change 09-28 close → 10-30 close | −982.14 |
| rebuilt: hold + fill + fees | −982.14 |
| largest single-session residual (34 sessions from 09-15) | 0.00 |

## Components

| component | USD |
|---|---:|
| hold (q_prev × close change) | −667.27 |
| of which NAV part (q_prev × close_prev × NAV return) | −2,250.74 |
| of which discount part (hold − NAV part) | +1,583.47 |
| fill (fills against that day's close), on $558,926.55 traded | −308.71 (−5.5bp) |
| regulatory fees, SEC + CAT | −6.16 |
| execution cost on paper, fill + fees | −314.87 (−5.6bp) |
| distributions paper did not book (long credited +956.04, short charged −635.19) | +320.85 |
| hold + fill + fees + distributions | −661.29 |

Notes:
- **Distributions** are the third score prod already computes
  (`dist_score.py`), reproduced here to the cent.
- **Ex-dates.** On an ex-date, the mechanical widening of the discount lands
  in the discount part: −61.28 long, +63.16 short, net +1.88. See the module
  docstring, EX-DATES.

## By period

The split comes after the EOD equity peak, which was measured at run time:
2026-10-12, equity 101,474.24.

| period | hold | NAV part | discount part | fill | fill bp | distributions |
|---|---:|---:|---:|---:|---:|---:|
| 09-15..10-12 | +1,476.73 | +225.69 | +1,251.04 | +0.03 | 0.0 | 0.00 |
| 10-13..10-30 | −2,144.00 | −2,476.43 | +332.43 | −308.74 | −9.5 | +320.85 |

## By group and side

| | hold | NAV part | discount part | fill | fill bp |
|---|---:|---:|---:|---:|---:|
| muni | −1,382.47 | −1,849.36 | +466.89 | −144.05 | −8.5 |
| multi | +26.47 | −1,100.05 | +1,126.52 | −128.44 | −4.8 |
| loan | +643.34 | +579.46 | +63.88 | −27.96 | −3.0 |
| hy | +45.39 | +119.21 | −73.82 | −8.26 | −2.6 |
| long side | −124.69 | −1,156.05 | +1,031.36 | −212.75 | −7.7 |
| short side | −542.58 | −1,094.70 | +552.12 | −95.96 | −3.4 |

The group column comes from `data/cef/cef_universe.csv`.

## What it says

1. **The signal's own leg, the discount part, earned +1,583.** It was positive
   in both periods, on both sides, and in every group but hy.
2. **The loss is NAV exposure the book does not choose to hold: −2,251.**
   - The muni group (short MQY/MHD) alone lost −1,849, after 10-13.
   - That period's NAV part (−2,476) is larger than the whole loss.
3. **Execution cost −315 (−5.6bp)** is about a third of the loss. It is
   concentrated after 10-13 (−9.5bp) and in munis (−8.5bp).

## Corrections for the record

These are the other session's documents. This note proposes the corrections
and edits nothing.

- **Paper charges regulatory fees on this account.** That contradicts CLAUDE.md
  landmine 1 and the paper rows of docs/REFERENCES.md ("no regulatory fees").
  - GET /v2/account/activities/FEE lists 37 REG (SEC) and CAT rows, summing to
    −6.16.
  - Each REG row's proceeds equal the session's value sold, and the per-session
    totals equal the modelled fees on 34 of 34 sessions.
  - Trap: with `until=2026-10-31` the 10-30 rows were missing, so `until`
    appears to filter on posting time.
- **The tool's first flat-start rule could never run on this account**
  (fixed in 25591d1). It demanded an unfunded session before the first EOD
  point, but the account has held $100,000.00 since at least 2026-05-04. The
  flat start is now shown by 11 sessions of unchanged equity, 09-14..09-28,
  before the first fill on 09-29.

## Panels and gaps

- NAV is yfinance `X{tk}X`. A stale copy (NAV of D−1 stamped D;
  results/cef/LIVE_NAV_QUALITY_2026-10-12.md) moves P&L between the NAV part
  and the discount part. It never changes hold, fill or the reconciliation.
- No share-count corporate action was found in the window for any traded name.
- No distribution day was UNMEASURED.

## Reproduce

```
QUANTT_ENV_FILE=<the cef key file> python3 scripts/cef/live_attribution.py fetch \
    --since 2026-09-14 --asof 2026-10-30 --cache-dir <outside the repo>
python3 scripts/cef/live_attribution.py analyse --cache-dir <same> --out-dir <outside the repo>
```

`fetch` is GET-only. It refuses to write under data/ or anywhere git can see.
