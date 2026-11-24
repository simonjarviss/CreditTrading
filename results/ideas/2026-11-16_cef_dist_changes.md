# Idea card — distribution cuts and raises in closed-end funds, read as dated events

**Slug:** `cef_dist_changes` · **Started:** 2026-11-16, **interrupted** that day (the editor was
force quit about 20 minutes in), **completed 2026-11-18** ·
**Status:** EXPLORE. The pre-specified cut REBOUND is refuted: a fund that cuts keeps falling
against the CEF market (−85bp over 20 sessions, t −5.5). The pre-specified RAISE drift is there
(+83bp over 20 sessions, t 4.3; book Sharpe 0.80 against the CEF market), but most of it is
earned in the first ten sessions after the declaration, so it stands or falls on learning the
declaration on time, which this test could not verify from a second source ·
**Reproducer:** `QUANTT_ENV_FILE=<env> python3 results/ideas/cef_dist_changes/explore.py`, then
`python3 results/ideas/cef_dist_changes/checks.py` ·
**Panels:** every CRSP closed-end fund, dead ones included, daily to **2025-12-31**
(`~/quantt_research/crsp_cef_daily.parquet`); `crsp_a_stock.stkdistributions` and closing bid and
ask from `dsf_v2` on R2, to **2025-12-31**; PCEF from Yahoo, fetched 2026-11-18. No NAV is used.
Licensed rows are not in the repository. Every figure below is [V], computed on 2026-11-18,
unless tagged.

## What the interruption left, and what was done on resuming

- On disk: `explore.py` with its full rule in the docstring, a whole `raw_dist.parquet`, and a
  **zero-byte `quotes.parquet`** (being written when the process died). No `results.json`, no
  card, no `checks.py`: no return had been read. The rule in the docstring is unchanged, word
  for word, and was run once.
- **Fix made after the interruption:** `stage()` accepted any file that existed. It now removes
  and re-pulls a staged file that does not open as parquet with rows. `quotes.parquet` was
  rebuilt (3,765,801 rows, last date 2025-12-31).
- **Counts differ from the docstring's.** The docstring quotes the first researcher's counts
  (10,935 changes of 5% or more, 8,211 from a stable base). The code as left counts 10,987 and
  8,003. I could not recover which earlier filter produced the docstring's figures; the run's
  own counts are used below.
- `checks.py` was written on 2026-11-18 **after** the returns were read. Nothing in it is
  pre-specified.

## The idea

A closed-end fund's holders buy it for income. Practitioners say that when a fund cuts its
regular distribution the price overshoots and recovers, and that a raise is followed by slow
drift up. The desk killed distribution data as a universe filter and inside its Kalman model
(`docs/RESEARCH_STATE.md`, "Distribution data"). It had never read the change as an event.

## What was fixed before the test (`explore.py` docstring)

- **Regular distribution:** CRSP `distype` 'CD', `disdetailtype` 'CDIV', `disfreqtype` 'M' or
  'Q'. Left out by code: 'SD' specials, 'CG' capital gains, 'ROC', 'CP', 'SP', 'FRS', and
  ordinary rows typed annual, semi-annual, year-end or unknown.
- **Event:** the declared regular amount differs from the previous one by 5% or more, the two
  amounts before it were within 5% of each other, same frequency, no split between, CRSP has a
  declaration date, first ex-date carrying that declaration. Raises with an ex-date from
  1 December to 15 January are left out (year-end extras typed as ordinary).
- **Timing:** D0 = first session on or after CRSP's declaration date; known at the close of
  K = D0 + 1; filled at K+1's close; earns K+2 to K+1+h, h = 20 and 60. Asserted in code.
- **Eligible:** price ≥ $2 and 21-session dollar volume ≥ $500,000, through K−1.
- **Book:** long the event funds equally, short the equal-weighted return of every eligible
  closed-end fund; flat under 3 names.
- **Controls:** the same funds' unchanged declarations; five correlation-matched funds of the
  same tax class with no change (CRSP has no fund category); five funds that moved as much
  against the market over the three sessions ending K.
- **Expected:** cuts fall 1% to 3% in the announcement window, then rebound by more than each
  control. Raises drift up.

## Counts

| | |
|---|---:|
| regular ex-dates since 2000, funds | 140,219 on 1,038 |
| declaration date missing | 0.64% overall; 14.7% in 2000, 3.9% in 2001, under 0.6% every year after |
| declaration date after the ex-date | 15 |
| changes of 5% or more | 10,987 |
| … with an acceptable series, a stable base, a sane ratio, a declaration date, first of its declaration | 7,635 |
| qualifying changes with no declaration date | 33 |
| cuts / raises in the panel | 4,575 / 3,035 (2,229 after the year-end rule) |
| **eligible cuts / raises** | **2,232 (86 a year, 521 funds) / 1,097 (42 a year, 395 funds)** |
| eligible, 2023–25 | 185 cuts (130, 11, 44), 219 raises (65, 123, 31) |

Median change −11.1% (cuts) and +10.7% (raises). Median 11 and 12 calendar days from
declaration to ex-date; the ex-date is a median of 7 sessions after K (10th to 90th
percentile 4 to 20).

## What it showed (gross, shift(2), no costs)

Announcement window, fund less CEF market, D0−1 to K+1 (four sessions, not tradable): cuts
**−130bp** (median −75bp, t −12.4); raises **+78bp** (median +64bp, t 7.9). The largest single
day is K itself (−85bp and +43bp), the session AFTER CRSP's declaration date, which agrees
with CRSP's date being about a session early against when the price moved.

Calendar-time book, long event funds against the CEF market, 2000-02 to 2025-12:

| | Sharpe (t) | return / vol | halves | 2002–08 | 2009–15 | 2016–19 | 2020–22 | 2023–25 | names; days on; long turnover |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| CUT, 20 sessions | **−0.94 (−4.78)** | −7.2% / 7.6% | −0.86 / −1.04 | −1.16 | −0.63 | −0.95 | −1.39 | −0.77 | 9.0; 72%; 33.7× |
| CUT, 60 sessions | −0.71 (−3.61) | −4.7% / 6.6% | −0.56 / −0.89 | −1.08 | −0.38 | −0.89 | −1.00 | −0.76 | 20.8; 97%; 15.3× |
| RAISE, 20 sessions | **0.80 (4.08)** | 5.3% / 6.6% | 0.59 / 1.04 | 0.54 | 0.97 | 0.33 | 1.46 | 0.78 | 6.2; 46%; 21.1× |
| RAISE, 60 sessions | 0.68 (3.47) | 4.5% / 6.6% | 0.42 / 1.01 | 0.06 | 0.88 | 0.26 | 1.21 | 1.18 | 11.8; 83%; 14.2× |

Controls, as books on the same dates, Sharpe (t):

| | CUT 20 | CUT 60 | RAISE 20 | RAISE 60 |
|---|---:|---:|---:|---:|
| unchanged declarations, same funds | −0.01 (−0.03) | −0.15 (−0.75) | 0.19 (0.95) | 0.04 (0.22) |
| correlation-matched peers | 0.18 (0.93) | 0.35 (1.76) | 0.45 (2.29) | 0.21 (1.05) |
| moved as much in the three sessions to K | 0.47 (2.41) | 0.16 (0.84) | 0.07 (0.33) | 0.06 (0.31) |
| long leg alone, no hedge | −0.07 (−0.38) | 0.20 (1.02) | 0.70 (3.57) | 0.92 (4.66) |
| long leg against PCEF, from 2010-02 | −0.75 (−2.98) | −0.48 | 1.01 (4.01) | 1.19 (4.75) |

Raise against PCEF by era (20 / 60 sessions): 2010–15 1.63 / 1.86, 2016–19 0.23 / 0.32,
2020–22 1.11 / 1.20, 2023–25 0.72 / 0.99.

Per event, buy and hold, fund less CEF market, t clustered by month of K:

| | n | mean | median | positive | t |
|---|---:|---:|---:|---:|---:|
| CUT, 20 sessions | 2,224 | −85bp | −80bp | 38.7% | −5.49 |
| CUT, 60 sessions | 2,221 | −137bp | −147bp | 39.5% | −4.75 |
| RAISE, 20 sessions | 1,097 | +83bp | +74bp | 60.8% | 4.32 |
| RAISE, 60 sessions | 1,091 | +99bp | +83bp | 56.1% | 3.04 |
| unchanged declarations (cut funds), 20 | 42,855 | −5bp | −6bp | 48.9% | −0.96 |
| unchanged declarations (raise funds), 20 | 36,197 | +1bp | −4bp | 49.3% | 0.16 |
| cut less its own five peers, 20 | 2,204 | −99bp | −85bp | 34.3% | −10.17 |
| raise less its own five peers, 20 | 1,083 | +71bp | +58bp | 60.8% | 6.06 |
| cut less five that fell as much, 20 | 2,224 | −99bp | −99bp | 38.1% | −6.34 |
| raise less five that rose as much, 20 | 1,097 | +99bp | +84bp | 61.7% | 4.88 |

Per event by era, 20 sessions (mean, t): cuts −153bp (−4.2), −63bp (−2.9), −48bp (−1.8),
−107bp (−2.3), −79bp (−1.2); raises +93bp (4.7), +71bp (2.0), +39bp (1.2), +144bp (2.4),
+33bp (1.1). Halves: cuts −96bp / −74bp; raises +83bp / +83bp.

Event-time path, fund less market (mean, t): cuts K+2..K+6 −26bp (−2.8), K+7..K+21 −54bp
(−2.9), K+22..K+61 −49bp (−1.9); raises +43bp (4.8), +39bp (2.4), +17bp (0.7).

**Liquidity and spread at K.** Cuts: median 21-session dollar volume $1.20M (10th percentile
$0.60M), median price $11.73, median market value $399M, closing spread median 19bp, mean
31bp, 90th percentile 53bp. Raises: $1.18M ($0.59M), $12.99, $464M, spread median 17bp, mean
26bp, 90th percentile 43bp. A quote on 99% of events; no event fund had zero volume at K or at
the fill. The 20-session effect is four to five times the median spread.

## Checks

Named in advance (`explore.py`):

| per event, 20 / 60 sessions | CUT | RAISE |
|---|---:|---:|
| entry and exit on closing mid quotes | −84bp (−5.4) / −142bp (−4.9) | +83bp (4.3) / +108bp (3.2) |
| one more skipped session | −74bp (−4.4) | +74bp (3.9) / +98bp (3.1) |
| fund's own ex-date week (X−3..X+3) earns nothing | −47bp (−4.0) / −60bp (−2.6) | +45bp (2.7) / +66bp (2.3) |
| municipal | −162bp (−4.7) / −201bp (−4.2) | −27bp (−0.6) / −124bp (−1.4) |
| taxable | −51bp (−2.9) / −108bp (−2.9) | +117bp (6.1) / +169bp (5.5) |
| monthly payers | −99bp (−6.1) / −148bp (−5.6) | +47bp (2.5) / +54bp (1.6) |
| quarterly payers | −26bp (−0.5) / −89bp (−1.1) | +195bp (5.1) / +243bp (3.8) |
| change 5–10% / 10–20% / over 20%, 20 sessions | −64 / −87 / −122bp | +62 / +106 / +94bp |
| dollar volume $0.5–2M / over $2M, 20 sessions | −81 / −98bp | +83 / +83bp |

- **Not bid-ask bounce and not stale closes.** Mid quotes give the same figure, a skipped
  session costs about 10bp, and the effect is the same above $2M a day.
- **Not the ordinary ex-date cycle, but the ex-date week carries about half of it.** The
  unchanged declarations sit at the same point of the cycle and earn nothing. Taking the
  fund's own seven ex-date sessions out of the window removes 45% of the 20-session figure
  for both cuts and raises, more than the 35% of sessions removed. The raise book with those
  sessions flat is 0.36 (t 1.85) at 20 sessions and 0.67 (t 3.40) at 60.
- **Not short-term reversal or momentum in the three-day move.** Funds that moved as much
  with no distribution news do the opposite or nothing.
- **Raises are a taxable-fund effect.** Municipal raises show nothing or negative.

Not pre-specified (`checks.py`, written after the returns were read):

| per event, fund less market, 20 sessions | CUT | RAISE |
|---|---:|---:|
| decided 5 sessions late | −61bp (−3.0) | +60bp (2.9) |
| decided 10 sessions late | −60bp (−3.3) | +30bp (1.8) |
| decided 20 sessions late | −55bp (−3.0) | +7bp (0.4) |
| decided at the EX-DATE close (the amount is public beyond argument) | −62bp (−2.8) | +31bp (1.5) |
| … 60 sessions | −67bp (−2.0) | +73bp (2.1) |
| … unchanged declarations anchored the same way, 20 | −4bp (−0.7) | +2bp (0.3) |
| … taxable only, 20 | −43bp (−1.6) | +56bp (3.4) |
| … municipal only, 20 | −102bp (−2.6) | −44bp (−0.7) |
| pre-specified window without the top and bottom 1% | −84bp | +80bp |
| K+62..K+121 (control beside it) | −56bp (−2.4); control −24bp | +21bp (0.8) |
| raises left out by the year-end rule, 20 / 60 | | +65bp (3.0) / +62bp (1.7) |

Books chosen after seeing the municipal split (flattered, shown only to size the idea):
taxable raises decided at K, 20 sessions, 0.94 (t 4.76) against the CEF market, 5.1 names, on
40% of days, halves 0.82 / 1.05, 0.99 against PCEF; the same decided at the ex-date close,
0.34 (t 1.71) at 20 sessions and 0.76 (t 3.84) at 60 (1.14 against PCEF from 2010).

- **The cut result does not depend on the date.** Decided 20 sessions late or at the ex-date
  it is still −55bp to −62bp over the next 20 sessions.
- **The raise result does.** It decays to nothing by 20 sessions late; from the ex-date only
  the 60-session, taxable version keeps a t above 2. So a late feed, or a CRSP declaration
  date that is earlier than the public announcement for some funds, would take most of it.
- A few events do not carry it: trimmed means are the same.
- The year-end rule discarded events that drift as much as the kept ones at 20 sessions; it
  was a caution, not a necessity.

## What I conclude

1. **The practitioner claim about cuts is wrong on this panel.** There is no rebound. A fund
   that cuts falls 130bp against the market in the announcement window and a further 85bp in
   the next 20 sessions and 137bp in the next 60, in every era, in both halves, on mid quotes,
   against every control, and whichever day it is dated from. Long-against-the-market after a
   cut, as pre-specified, is KILLED at −0.94.
2. **What that is worth to the desk is a list to avoid, not a book.** The short side needs a
   borrow most closed-end funds do not have, and this test has no borrow data. The usable
   reading: the core discount book should not treat a fresh cut's wider discount as a buy for
   at least 60 sessions. That is a proposal for a test on the core book's own funds with NAVs,
   not something shown here (no NAV was used, so discount and NAV moves are not separated).
3. **The raise drift is positive as pre-specified** (0.80, t 4.1; +83bp per event; 1.0 against
   PCEF since 2010; long-only 0.70), in taxable funds, with about 42 events a year and spreads
   under a quarter of the effect. It is weak in 2016–19 (0.33) and per event in 2023–25
   (+33bp, t 1.1).
4. **Main artifact risk: the declaration date.** The test relies on CRSP's declaration date
   plus one session being public. The largest reaction is on K, which is consistent with that,
   and the direction survives ex-date dating, but half or more of the raise return is in the
   first ten sessions and is gone if the news arrives late. I could not check CRSP's dates
   against the funds' own press releases: closed-end funds do not file them on EDGAR as 8-Ks,
   and no dated press-release source is in the desk's data.
5. **Shadow book: not yet.** A live feed that lists a declared amount within a session or two
   has not been shown to exist. The repo's own notes on Alpaca's corporate-actions feed say a
   cash dividend is filed under a process date near its PAYABLE date and that Alpaca gives no
   guarantee on creation time [S: `quantt/broker/alpaca.py`, `distributions` docstring;
   `shadow/sources.py`]. Whether a declared dividend appears there before its ex-date was not
   measured here (no broker call was allowed in this lane). If it appears only by the
   ex-date, the tradable form is the ex-date-anchored one: +31bp (t 1.5) at 20 sessions,
   +73bp (t 2.1) at 60, which is not enough to promote.

## What would reopen it

- Measure, for 30 recent raises, the day Alpaca's corporate-actions feed first lists the new
  amount against the fund's press release. If it is within two sessions of the declaration,
  the pre-specified raise book is a shadow candidate (taxable funds; about 40 to 70 events a
  year recently).
- A dated press-release source (fund-sponsor sites or a newswire archive) to audit CRSP's
  declaration dates on a sample of both signs.
- The cut as a gate on the core book: on the desk's NAV panels, does the discount of a fund
  that cut keep widening for 60 sessions, or is the underperformance NAV? Counted as a
  re-test of the dead "distribution data" line, with that history stated.
- Borrow availability for cut funds at Alpaca on the day, which would turn the avoid list
  into a short against PCEF.

## Could not do

- Verify declaration dates against a second source (above).
- Separate discount from NAV: CRSP has no NAV, and Yahoo's NAV series covers live funds only;
  not attempted.
- A true category-matched control: CRSP has no fund category; correlation-matched funds of
  the same tax class stand in for it.
- Read the Alpaca feed's timing.

**Files:** `results/ideas/cef_dist_changes/explore.py`, `checks.py`, `results.json`,
`checks.json`, `equity.png`. **Not independently reviewed.**
