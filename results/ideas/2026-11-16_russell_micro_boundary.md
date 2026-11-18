# Idea card — The bottom edge of the Russell 2000, predicted from public ranks: the flow is real, the return is not

**Slug:** `russell_micro_boundary` · **Started:** 2026-11-16, **interrupted** that day about
20 minutes in (the editor was force quit), **completed 2026-11-18** ·
**Status:** SET ASIDE. Buying predicted additions before reconstitution earns nothing over
IWM (+0.5% a year, t 0.5) and less than neighbours that do not change membership. The
reversal afterwards (deletions over additions) is +1.8% over 20 sessions (t 1.2 on 25
years) and +4.0% over 60 (t 1.4), with the deletions leg alone at −0.1% and +1.8% (t 0.8)
and half of the 60-session figure from 2009 ·
**Reproducer:** `QUANTT_ENV_FILE=<env> python3 results/ideas/russell_micro_boundary/stage.py`,
then `python3 results/ideas/russell_micro_boundary/explore.py` and `checks.py` ·
**Panels:** CRSP daily file on R2 (delisted shares included), months March to October of
2001 to 2025, last row **2025-10-31** (CRSP itself ends 2025-12-31); Compustat header
country through the CCM link; IWM total return from Yahoo (`~/quantt_research/yf_daily.parquet`,
last date 2026-11-09, used to 2025-10-31). Licensed rows are under
`~/quantt_research/russell_micro_boundary/`, not in the repository.

## State found on resuming, and what was done after the interruption

- On disk: `stage.py`, `universe.py`, `explore.py` (rule in the docstring, dated
  2026-11-16), `rankdays.parquet` (130,508 rows, 26 rank days, opens cleanly) and a
  **zero-byte `daily.parquet`**. No `results.json`, no card: **no return had been read.**
  The rule in `explore.py` and `universe.py` is therefore the pre-specified rule and was run
  unchanged, once.
- `daily.parquet` was deleted and rebuilt by `stage.py` (10,771,408 rows, 6,125 shares,
  2001-03-01 to 2025-10-31). No script was edited. No bug fix was needed.
- `checks.py` was written on 2026-11-18 after the first run; nothing in it is pre-specified.

## The idea

Each June the Russell 2000 is rebuilt from a ranking by market value taken on a rank day
some weeks earlier. Index funds buy what enters and sell what leaves at the reconstitution
close. The top edge is crowded; the bottom edge (companies crossing rank 3000, about $100M
to $200M) is too small for large funds. The ranking is public arithmetic, so a small book
could front-run the additions and then trade the reversal. No Russell test was in
`results/ideas/` or the KILLED table.

## What was fixed before any return was read

- **Calendar.** Rank day: last session of May to 2016; then the dates FTSE Russell
  published (2017-05-12 … 2025-04-30; 2020-05-08 is recalled, not confirmed [U]).
  Reconstitution day F: last session of June 2001–03; last Friday of June 2004–06; from
  2007 the Friday before if the last Friday is the 28th–30th (29th–30th from 2013) [S: FTSE
  Russell reconstitution timeline, fetched 2026-11-16 by the first researcher].
- **Prediction.** CRSP common shares listed on NYSE, NYSE American or Nasdaq, US
  incorporated or US headquartered; share classes summed by company; price ≥ $1 and
  company value ≥ $30M; ranked by company value on rank day. Predicted Russell 3000 =
  ranks 1–3000. **No band at rank 3000** (the 2007 banding rule is documented for the
  1000/2000 breakpoint; whether any applies at 3000 could not be confirmed [U]).
- **Sets** (a share must be listed on both this and last year's rank day): ADD (not a
  predicted member last year, rank 2501–3000 now), DEL (member last year, rank 3001–3500
  now), controls STAY_IN (member, rank 2501–3000) and STAY_OUT (non-member, rank
  3001–3500).
- **Test A:** long ADD, equal weights, short IWM; decided at the rank-day close, filled
  next close, held to the close before F. **Test B:** long DEL / short ADD, entered at the
  F close, 20 and 60 sessions; DEL against IWM alone also reported.
- **Controls:** the stayers in the same windows; the same shares one year later.
- **Expected:** A positive and above STAY_IN, larger before 2010; B positive over 20
  sessions, DEL above STAY_OUT, weaker at 60.

## Is the prediction any good? [V]

It cannot be checked against the licensed lists. The one available test is reconstitution-day
dollar volume against the share's own 21-session median up to rank day:

| set | a year | price | company value | 21-day dollar volume | closing spread | F-day volume multiple | share at 5× or more |
|---|---:|---:|---:|---:|---:|---:|---:|
| ADD | 131 (43–269) | $10.44 | $179M | $653,000 | 0.53% | 14.6× | 72% |
| DEL | 104 (71–212) | $4.63 | $110M | $557,000 | 0.52% | 10.7× | 67% |
| STAY_IN | 321 | $9.69 | $208M | $805,000 | 0.33% | 4.1× | 42% |
| STAY_OUT | 335 | $7.15 | $84M | $144,000 | 1.03% | 1.2× | 15% |

Medians on rank day. A week before F the multiples are 1.1× to 1.8×. So the predicted
crossers do get the index trade and the predicted outsiders do not: roughly seven in ten
predicted changes look right, about one in seven "outsiders" looks like a missed addition.
ADD within 100 ranks of the cut is confirmed only 51% of the time against 80–84% further
away, which is where an unseen float adjustment would bite. The company value at predicted
rank 3000 runs from $72M (2009) to $328M (2021); `checks.json` has each year, not compared
with FTSE Russell's published breakpoints (none fetched).

## What it showed (gross, shift(2), no costs) [V]

Each book is 100% long the set and 100% short IWM inside its window and flat outside; one
event a year, turnover 4.0 times notional a year (in and out, both legs). "A year" is the
mean of the 25 yearly sums of P&L; its t is on those 25 numbers, which is the honest one.
The Sharpe and its t are on all daily rows (flat days included).

**Test A, before reconstitution (rank day + 1 to F − 1)**

| | Sharpe (t) | return / vol | a year (t, years up) | halves | 2001–08 | 2009–15 | 2016–19 | 2020–22 | 2023–25 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ADD against IWM | 0.10 (0.51) | 0.5% / 4.9% | +0.5% (0.54, 10/25) | 0.40 / −0.10 | +1.6% | +0.4% | −1.3% | +5.9% | −5.1% |
| STAY_IN, the control | 0.43 (2.16) | 1.3% / 3.0% | +1.3% (2.27, 17/25) | 0.43 / 0.44 | +0.6% | +1.4% | −1.5% | +5.1% | +2.7% |
| ADD less STAY_IN | −0.14 (−0.70) | −0.8% / 5.6% | −0.8% (−0.89, 9/25) | 0.11 / −0.32 | +1.0% | −1.0% | +0.1% | +0.8% | −7.8% |
| same shares a year later | 0.08 | | +0.3% (0.35) | | | | | | |

Per name, buy and hold less IWM (3,267 events): mean +0.49%, median −0.35%, 49% up;
bought at the closing ask and sold at the closing bid, −0.36%. Held into the F close
instead (stated variant): ADD +0.8% a year (t 0.76), ADD less STAY_IN −1.5% (t −1.46).

**Test B, after reconstitution (entered at the F close)**

| | Sharpe (t) | return / vol | a year (t, years up) | halves | 2001–08 | 2009–15 | 2016–19 | 2020–22 | 2023–25 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 sessions: DEL less ADD | 0.30 (1.48) | 1.8% / 6.2% | +1.8% (1.19, 15/25) | 0.41 / 0.15 | +0.7% | +2.6% | −1.1% | +7.1% | +1.7% |
| DEL against IWM (long leg alone) | −0.02 (−0.12) | −0.1% / 5.3% | −0.1% (−0.12, 12/25) | 0.20 / −0.31 | −0.0% | +0.6% | −3.7% | +0.7% | +1.6% |
| DEL less STAY_OUT | 0.12 (0.62) | 0.6% / 5.2% | +0.6% (0.56, 14/25) | 0.27 / −0.01 | −0.7% | +1.4% | −1.7% | +3.1% | +3.0% |
| ADD against IWM (a short earns the opposite) | −0.56 (−2.79) | −2.0% / 3.5% | −2.0% (−2.03, 11/25) | −0.49 / −0.62 | −0.7% | −1.9% | −2.6% | −6.4% | −0.1% |
| ADD less STAY_IN | −0.35 (−1.72) | −1.3% / 3.8% | −1.3% (−1.29, 12/25) | −0.37 / −0.32 | −0.2% | −1.6% | −0.1% | −3.9% | −2.4% |
| DEL less ADD, one-session skip | 0.22 (1.12) | | +1.3% (0.92, 15/25) | 0.23 / 0.22 | −0.4% | +1.5% | +0.2% | +6.5% | +1.7% |
| DEL less ADD, same shares a year later | 0.05 | | +0.2% (0.30) | | | | | | |
| 60 sessions: DEL less ADD | 0.42 (2.09) | 4.0% / 9.6% | +4.0% (1.41, 17/25) | 0.59 / 0.23 | −0.5% | +10.6% | +2.2% | +9.1% | −1.8% |
| DEL against IWM (long leg alone) | 0.22 (1.08) | 1.8% / 8.4% | +1.8% (0.84, 14/25) | 0.40 / −0.01 | −0.1% | +6.2% | −0.4% | +2.6% | −1.1% |
| DEL less STAY_OUT | 0.27 (1.34) | 2.1% / 7.9% | +2.1% (0.93, 16/25) | 0.47 / 0.08 | −1.0% | +5.5% | +1.1% | +3.7% | +2.1% |
| DEL less ADD, same shares a year later | −0.18 | | −1.3% (−0.92) | | | | | | |

Per name, buy and hold less IWM:

| | events | mean | median | up | bought at ask, sold at bid |
|---|---:|---:|---:|---:|---:|
| DEL, 20 sessions | 2,596 | +0.07% | −1.18% | 47% | −1.14% |
| DEL, 60 sessions | 2,596 | +2.74% (+0.66% without the 20 best) | −1.28% | 48% | +1.63% |
| ADD, 20 sessions | 3,224 | −1.45% | −2.05% | 43% | −2.17% (as a long) |
| STAY_IN, 20 sessions | 7,985 | −0.78% | −1.29% | 44% | |
| STAY_OUT, 20 sessions | 8,303 | −0.88% | −2.05% | 42% | |

Against the expectations: A failed (not positive in any useful sense, below its control,
no early-era effect to decay: +1.6% in 2001–08 against a control at +0.6%). B has the
expected sign but not the size: 20 sessions is t 1.2 on years, the long leg alone is zero,
and 60 sessions is larger, not weaker, which is not what an index-flow bounce looks like.

The stated liquidity split ($500,000 a day on rank day) does not rescue it: liquid DEL
against IWM is +0.0% (20) and +3.2% (60, t 1.13); liquid ADD less liquid STAY_IN before
reconstitution is −0.6%. One cell stands out, liquid DEL less liquid STAY_OUT over 60
sessions at +7.4% a year (t 3.21, 21/25), but it comes from the control falling (liquid
STAY_OUT −4.2% against IWM), not from deletions rising, and it is one of some forty cells.

## Checks that were not pre-specified (`checks.py`) [V]

| | a year (t on years) | without its two best years |
|---|---:|---:|
| 20 sessions, DEL less ADD | +1.8% (1.19) | +0.7% (0.50) |
| 60 sessions, DEL less ADD | +4.0% (1.41); 2009 alone is +54% | +1.5% (0.70) |
| 60 sessions, DEL against IWM | +1.8% (0.84); 2009 alone is +40% | −0.4% (−0.29) |
| 20 sessions, ADD less STAY_IN | −1.3% (−1.29) | −0.5% (−0.53) |
| volume-confirmed, entered F+1, 20 sessions: DEL less ADD | +3.0% (1.62) | +1.2% (0.84) |
| volume-confirmed, 60 sessions: DEL less ADD | +5.3% (1.93) | +2.9% (1.28) |
| volume-confirmed DEL against IWM, 20 / 60 sessions | +0.7% (0.63) / +3.1% (1.52) | −0.4% / +1.1% (0.70) |
| confirmed DEL less unconfirmed DEL, 20 / 60 | +2.4% (1.68) / +3.9% (1.97) | +1.3% / +2.0% |
| STAY_IN less STAY_OUT, rank day to the F close | +1.5% (2.03, 19/25) | +1.0% (1.39) |
| the same, shares one year later | +0.3% (0.44) | |

- **A few years carry the reversal.** Take out 2009 and one other year and nothing is
  left at either horizon. The 60-session long leg is a lottery: mean +2.7% a name, median
  −1.3%.
- **Confirming membership by F-day volume helps a little, as it should if the flow is the
  cause.** "Confirmed" means a share traded at least five times its usual volume on F,
  decided at the F close and filled at F+1 (so this also carries the skip day). Confirmed
  deletions beat unconfirmed ones by 2.4% over 20 sessions (t 1.7) and the confirmed spread
  is +3.0% (t 1.6). The direction is right and it is still not significant on 25 events;
  confirmed deletions at the quote lose 0.7% a name over 20 sessions.
- **The steadiest thing in the run is not the idea.** Bottom-zone members that stay rose
  against IWM into the reconstitution close: +2.3% a year, 20 of 25 years (per name +1.9%
  mean, +0.5% median, +1.0% at the quote), +1.5% over non-members just below (t 2.0), and
  the same shares a year later show +0.3%. That was found by looking, among dozens of
  comparisons, and its t of 2 is what such a search throws up. Recorded, not claimed.
- **Stale prices and bounce.** Held name-days with no CRSP return are 0.6% (ADD) and 0.3%
  (DEL) of the 20-session books, and zero-volume days 1.4% and 0.9%; they are booked as
  zero and counted. The skip-day and at-the-quote figures above are the bounce test: the
  20-session DEL long is +0.07% at closes and −1.14% at the quote.
- **Did the bottom edge decay like the top?** There was no early effect to decay: test A
  is +1.6% in 2001–08 (control +0.6%), the reversal +0.7% over 20 sessions. The F-day
  volume multiple of additions is 13× in 2001–08 and 13× in 2023–25, so the flow has not
  gone; it just is not priced in a way this rule captures.

## Liquidity and capacity

Additions and deletions trade $0.4M to $1.4M a day by era (median) with a closing spread
of 0.4% to 0.7% (mean 0.9%); 7–8% trade under $100,000 a day. A $100k to $1M book spread
over 100 names is $1,000 to $10,000 a name, which fits. The short side of B (additions,
$179M companies) may not be easy to borrow at Alpaca: not tested, and the long leg alone
has no result to protect.

## What I conclude

1. **Front-running the bottom-edge additions from public ranks does not pay** under
   next-close fills: nothing over IWM, less than stayers, no era in which it clearly worked.
   The prediction is not the problem (72% confirmed by volume).
2. **The post-reconstitution reversal has the right sign and no significance** on the only
   sample size that matters (25 events), sits in the short leg and in 2009, and its long
   leg is zero at 20 sessions and a lottery at 60.
3. Set aside, not killed: the flow is demonstrably there (10–15× volume) and confirmed
   deletions do better than unconfirmed ones, so a sharper membership list could move it.

## What would reopen it

- The actual preliminary add/delete lists FTSE Russell publishes in June (dated, public
  after the close), instead of a prediction that is right seven times in ten; they would
  also allow an entry at the list date rather than rank day.
- Closing-auction imbalance on F for these names, to buy only deletions that were actually
  hit.
- A written, single-claim test of the stayers observation on other index bottoms (S&P 600,
  Russell Microcap), made before looking.

## What could not be done

- No check against true membership; float adjustments and the exact eligibility rules by
  year are not reproduced. The headquarters country is today's Compustat header (a small
  lookahead in the universe only, stated in `universe.py`).
- Whether a band applies at rank 3000, and the 2020 rank day, are unconfirmed [U].
- Borrow for the additions was not checked.

**Not independently reviewed.**
