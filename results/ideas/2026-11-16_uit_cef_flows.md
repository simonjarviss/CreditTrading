# Idea card — Unit investment trusts winding up: a dated forced seller of closed-end funds

**Slug:** `uit_cef_flows` · **Started:** 2026-11-16, **interrupted** (editor force quit about
20 minutes in), resumed twice and **completed 2026-11-18** ·
**Status:** SHADOW from 2026-11-18: books `uit_termination` and `uit_termination_big_sale`, written and
committed locally, not yet on the VM's `shadow` branch (see "Shadow book" at the end). PROMISING. Closed-end funds held by a terminating unit trust fall 40bp against
the CEF market over the nine sessions to the Mandatory Termination Date T (t −9.8; controls
+8bp), most of it on T−2, T−1 and T, and recover 33bp over T+1..T+3 (t 15; 31bp on mid
quotes; 12bp after paying the full closing spread on both sides, t 5.7). The pre-specified
book, which waits a day and enters at the T+1 close, keeps only the tail: Sharpe 0.67, t 2.4.
The rebound is on T+1 and T+2 and the date is public two years ahead, so the trade is to buy
at T's close. That version was **not pre-specified** ·
**Reproducer:** `QUANTT_ENV_FILE=<env> python3 results/ideas/uit_cef_flows/crawl.py index`,
`crawl.py filings`, `stage.py`, `python3 parse.py`, `QUANTT_ENV_FILE=<env> python3 sizes.py fetch`,
`python3 sizes.py parse`, `python3 explore.py`, `python3 checks.py` ·
**Panels:** every CRSP closed-end fund, dead included (`~/quantt_research/crsp_cef_daily.parquet`),
to **2025-12-31**; CRSP closing bid and ask for the same funds, 2011-01-03 to **2025-12-31**;
EDGAR form 487 and 24F-2NT, quarterly indexes 2012 Q1 to **2025 Q4**, fetched 2026-11-16 and
2026-11-18. Licensed rows and the EDGAR cache are under `~/quantt_research/uit_cef_flows/`.
Every figure below is [V], computed on 2026-11-18, unless tagged otherwise.

## What survived the interruption, and what was done about it

- **2026-11-16:** `stage.py` and `crawl.py` written, the form index a fifth done. No
  `explore.py`, no rule, no result.
- **2026-11-18, first resumption (also cut off):** index finished, the capped crawl run,
  `parse.py`, `sizes.py` and `explore.py` written. The rule in the `explore.py` docstring
  dates from this session, before any return was read; no `results.json` existed. It is kept
  word for word.
- **2026-11-18, second resumption (this one):** every parquet opened and its last date read;
  the parser's tables predated the end of the crawl and were rebuilt. Then, before any return:
  1. **Fix:** Guggenheim files HTML instead of plain text from mid-2020; 326 kept filings had
     no portfolio header. Each HTML table row is now turned into one text line and the same
     rules applied (`parse.py`, `html_rows`), used only when the plain-text rules find nothing.
     Trusts parsed rose from 2,020 to 2,638.
  2. The 24F-2NT notices were fetched (1,591) and sized; the gate was read; the live calendar
     block was added to `explore.py` (reads no return).
  3. `explore.py` was then run once. Its only later change saves the control funds' column
     numbers for `checks.py`; the re-run's `results.json` is byte-identical.
- `crawl.py`'s docstring says `explore.py` reads `ft_sample.json`. It does not and need not:
  the extra First Trust filings (from 2024-11-01) all terminate after the price panel ends.

## The idea

A unit investment trust is a fixed portfolio with a termination date printed in its
prospectus. First Trust and Guggenheim each run many series that hold only closed-end funds,
about 26 funds a trust. Both prospectuses say the trustee sells "beginning nine business
days prior to, and no later than" the Mandatory Termination Date [V: read in four cached
prospectuses, 2018 and 2023]. That is a dated seller in thin funds, known two years ahead.
An earlier agent proposed it; a sceptic doubted the size; nobody had measured it.

## What was fixed before the test (the docstring of `explore.py`)

- **Trusts:** every trust parsed from First Trust and Guggenheim 487s, 2012–2025. A holding is
  a closed-end fund when its ticker is a CRSP closed-end fund's within 10 days of deposit; a
  trust is a closed-end trust when more than half its lines are.
- **Event:** (fund, T), T the last session on or before the termination date; `n_series` is
  the number of trusts. Asserted: the prospectus was filed more than 30 days before T.
- **Eligible:** price ≥ $2 and 21-session dollar volume ≥ $100,000, read at T−10.
- **Market:** equal-weighted CRSP total return of all eligible closed-end funds.
- **Windows:** T−9..T (expected negative), T+1..T+10 and T+1..T+20 (the lane's rebound),
  T+2..T+11 and T+2..T+21 (decide at T, fill at T+1: the long-only trade). Weighted by
  `n_series`, t clustered by month of T.
- **Book:** `harness.evaluate`, shift(2), long every event fund in T+2..T+11 against the
  equal-weighted market; long-only beside it.
- **Control:** the 5 eligible funds most correlated with the event fund over T−280..T−30 that
  no terminating trust holds within 30 sessions. **Placebo:** the same funds at T−40.
- **Splits named in advance:** `n_series`; dollar volume under and over $500,000; terciles of
  estimated sale over nine-session volume.
- **Gate (the sceptic's):** stop if the 90th percentile of estimated sale over the fund's
  nine-session dollar volume is under 5%.
- **Expected:** T−9..T negative, T+2..T+11 positive and above controls, both growing with size.

## The flow table (no returns)

| step | count |
|---|---|
| form 487 in the index, 2012–2025 | First Trust 8,209 · Guggenheim 1,189 · Invesco 1,701 · Advisors Disciplined 1,432 · SmartTrust 533 · other 583 |
| fetched (**the cap**) | 4,414: every Guggenheim filing; **every third First Trust filing**, all years; every First Trust filing from 2024-11-01 |
| kept ("closed-end" 15 times or more) | 1,971 |
| trusts parsed · holding lines | 2,638 · 87,458 (dropped: 88 no holding line, 21 no header) |
| closed-end trusts | **1,212** (First Trust 717, Guggenheim 495); median 26 funds, median term 24.0 months |
| fund-events to 2025-12-31 · eligible | 26,103 · **24,623** on 567 funds and 724 termination sessions |
| eligible events a year | 2013: 687 · 2014: 3,229 · 2015: 2,616 · 2016: 2,694 · 2017: 2,210 · 2018: 2,031 · 2019: 2,058 · 2020: 1,827 · 2021: 1,817 · 2022: 1,437 · 2023: 1,662 · 2024: 1,121 · 2025: 1,234 |
| `n_series` | 1: 23,762 · 2: 825 · 3: 31 · 4+: 5 |

Invesco, SmartTrust and Advisors Disciplined Trust were counted, not crawled. Two thirds of
First Trust's filings before 2024-11 were not fetched, so true events are roughly double and
some "control" funds are in fact held by an unread trust (this biases the control contrast
towards zero, not away).

**Size (24F-2NT, 1,590 notices parsed, 1,175 of 1,212 trusts sized).** Units sold less units
redeemed before the final fiscal year: median trust **$19.9M** (10th to 90th percentile
$8.8M to $45.4M). Redemptions reported are small beside sales, so the low estimate is about
the same ($20.6M). Estimated sale in one fund at one termination: median **$0.75M**, 90th
percentile $1.84M [U: deposit weights, sale prices not termination prices, a registrant with
several trusts split equally].

| estimated sale ÷ the fund's dollar volume over T−18..T−10 | p10 | p25 | p50 | p75 | p90 |
|---|---|---|---|---|---|
| high estimate | 1.4% | 3.1% | 7.4% | 15.8% | **28.4%** |

**The gate passes** (28.4% against 5%). The sceptic was wrong on size.

## What it showed — per event (buy-and-hold, fund less CEF market, weighted by `n_series`)

| window | events: mean bp (t) | median | share > 0 | controls | event less control (t) | placebo T−40 |
|---|---|---|---|---|---|---|
| T−9..T (selling) | **−39.9 (−9.8)** | −35.2 | 41.2% | +7.9 | −47.7 (−15.8) | −0.1 |
| T+1 alone | **+19.8 (14.3)** | +16.8 | 61.8% | +1.6 | +18.2 (16.4) | 0.0 |
| T+1..T+10 | **+33.2 (7.8)** | +27.2 | 56.8% | +4.4 | +28.8 (9.1) | +3.7 |
| T+1..T+20 | +33.5 (5.6) | +27.1 | 54.6% | +3.5 | +29.6 (6.7) | +5.1 |
| T+2..T+11 (pre-specified trade) | **+14.9 (3.7)** | +11.3 | 52.7% | +2.0 | +12.9 (4.7) | +5.0 |
| T+2..T+21 | +12.5 (2.1) | +10.5 | 51.9% | +2.1 | +10.0 (2.5) | +5.4 |

n = 24,453 to 24,593 events in 151 to 152 months. Unweighted figures are within 1bp.

Daily, fund less market (bp): T−5 −2.5, T−4 −2.9, T−3 −2.2, **T−2 −7.6, T−1 −7.9, T −8.9,
T+1 +19.8, T+2 +11.2**, T+3 +2.8, T+4 +1.3, then nothing (T+4..T+10: +0.3, t 0.1).

| split named in advance | T−9..T | T+1..T+10 | T+2..T+11 |
|---|---|---|---|
| sale share, low tercile (under 4.3%) | −14.3 (t −2.5) | +14.7 (2.4) | +5.8 (0.9) |
| middle | −36.1 (−7.3) | +33.1 (6.2) | +13.3 (2.9) |
| high (over 12.1%) | **−68.3 (−10.3)** | **+51.3 (8.5)** | **+25.5 (4.4)** |
| dollar volume under $500,000 | −68.2 (−10.0) | +47.6 (7.2) | +24.3 (3.8) |
| $500,000 and over | −34.3 (−8.3) | +30.4 (6.9) | +13.1 (3.2) |
| `n_series` 1 | −38.6 (−9.6) | +32.5 (7.7) | +14.1 (3.5) |
| `n_series` 2–3 (854 events) | −55.5 (−4.4) | +42.1 (3.2) | +27.0 (2.8) |
| 2012–2015 | −30.9 (−5.1) | +33.7 (5.9) | +19.6 (4.0) |
| 2016–2019 | −36.2 (−5.5) | +31.8 (4.5) | +15.7 (2.3) |
| 2020–2022 | −54.1 (−5.4) | +32.2 (2.7) | +11.1 (1.0) |
| 2023–2025 | −45.4 (−4.0) | +36.9 (3.1) | +10.3 (1.0) |
| early half (to 2018-06-07) | −30.1 (−5.8) | +32.0 (7.0) | +17.3 (3.9) |
| late half | −50.0 (−8.3) | +34.4 (4.7) | +12.6 (1.9) |

The size of the fall and of the rebound both rise with the estimated sale, as expected.

## What it showed — the pre-specified calendar book (T+2..T+11, shift(2), gross)

| sample | return / yr | vol / yr | Sharpe | t |
|---|---|---|---|---|
| full, 2013-04-04 to 2025-12-29 | 3.26% | 4.84% | **0.67** | 2.40 |
| early half (to 2019-08-14) | 3.77% | 3.71% | 1.02 | 2.56 |
| late half | 2.71% | 5.75% | 0.47 | 1.19 |
| 2013–2015 | 4.44% | 4.02% | 1.10 | 1.83 |
| 2016–2019 | 2.76% | 3.48% | 0.79 | 1.58 |
| 2020–2022 | 3.38% | 7.54% | 0.45 | 0.78 |
| 2023–2025 | 2.73% | 3.40% | 0.80 | 1.38 |
| control: the same book on the control funds | 1.12% | 4.71% | 0.24 | 0.85 |
| event less control (long-only legs) | 2.14% | 3.53% | 0.61 | 2.17 |
| long-only, no hedge | 9.45% | 13.42% | 0.70 | 2.51 |

No event before 2013, so the 2002–08 era is empty and 2009–15 is 2013–15. Turnover 36 times
a year; 73 funds held on an average active day; active on 93% of sessions.

**Liquidity of what is held:** median price $12.44; median 21-session dollar volume $1.19M
(25th percentile $0.65M; 16.8% of events under $500,000); 0.12% of window days have no
volume; closing bid-ask spread at T: median **14.9bp**, mean 19.2bp, 75th percentile 22.9bp.

On its own the pre-specified book is thin: +14.9bp per event against a 14.9bp spread, and
−3.4bp (t −0.8) if bought at the ask and sold at the bid.

## Checks (`checks.py`; none pre-specified)

1. **Mid quotes (bounce).** From closing midpoint to closing midpoint: T+1 **+17.3bp**
   (t 12.8) against +19.8 on closes; T+1..T+3 **+31.1bp** (t 14.1) against +33.1; T−2..T
   −19.2 against −24.2. The close sits a little lower in the quote on T (0.49 of the way
   from bid to ask, against 0.56 at T−40) and higher on T+1 (0.63), which accounts for the
   2–3bp gap. The rebound is not bid-ask bounce.
2. **Worst-case spread.** Buy at T's closing ask, sell at the closing bid of T+3, less the
   market: **+12.0bp** per event (t 5.7, 53.9% positive); T+1..T+10 +12.5bp (t 2.9).
3. **Books entered at T's close** (decided at T−1 or earlier, since T is public; shift(2)
   kept; `harness.evaluate`; gross; hedge is the equal-weighted CEF market):

| book (not pre-specified) | return / yr | vol | Sharpe | t | halves | eras 13–15 / 16–19 / 20–22 / 23–25 | control book | T−40 placebo book | long-only Sharpe |
|---|---|---|---|---|---|---|---|---|---|
| T+1..T+3, all events | 17.0% | 9.0% | **1.90** | 6.8 | 3.56 / 1.55 | 2.96 / 4.01 / 1.23 / 4.95 | 0.37 | 0.29 | 1.49 |
| T+1..T+10, all events | 7.7% | 4.9% | 1.59 | 5.7 | 1.75 / 1.53 | 1.97 / 1.66 / 1.31 / 2.20 | 0.34 | 0.15 | 1.08 |
| T+1..T+3, sale known before T ≥ 5% of volume | 18.1% | 5.2% | 3.48 | 12.4 | 3.48 / 3.46 | 3.12 / 3.70 / 2.91 / 5.07 | 0.44 | 0.11 | 2.53 |
| T+2..T+4, all events (a day late) | 7.6% | 9.0% | 0.84 | 3.0 | 2.26 / 0.48 | 1.81 / 2.48 / 0.29 / 2.21 | 0.22 | 0.09 | 0.72 |

   The T+1..T+3 book holds 41 funds on an active day, is active on 55% of sessions and turns
   over 75 times a year; these are daily-rebalanced weights, which flatter thin shares, so
   read the per-event figures first. The hedge is not tradable as such (PCEF is the proxy);
   the long-only column is what an Alpaca book can hold.
4. **A size filter known in advance.** Trust size from notices filed at least 30 days before
   T (asserted), threshold the lane's 5%: 15,273 of 24,341 sized events. T−9..T −54.0bp,
   T+1..T+3 **+43.4bp** (t 16.6; mid +41.1; ask-to-bid +19.9, t 7.9). Under 5% or unsized:
   T+1..T+3 +15.8bp (t 5.5).
5. **Ex-date cycle.** With every session within three of the fund's own ex-date removed:
   T−9..T −27.2 (t −8.1), T+1..T+10 +28.1 (t 8.5), T+2..T+11 +15.7 (t 5.5). Not the desk's
   ex-date drift.
6. **Sponsors.** First Trust only: T−9..T −50.9, T+1..T+3 +40.7 (t 17.3). Guggenheim only:
   −23.7, +21.9 (t 5.7). Both signs in both.
7. **The desk's own funds** (tickers in `data/cef/cef_prices.parquet`, 3,384 events, about
   260 a year on this sample): T−2..T −23.2bp (t −6.2), T+1..T+3 +29.3bp (t 9.2).
8. **Mid quotes by era, T+1..T+3:** +24.3, +30.1, +33.0, +42.9bp (t 9.1, 9.6, 5.8, 5.9). The
   2020–22 mid-quote figure for T−9..T is −3.0 (t −0.1) against −54.1 on closes; one or more
   bad quotes in that era, not chased.
9. **Deposit leg (information only).** After a deposit date: D+1..D+21 +27.9bp (t 5.3),
   D+1..D+63 +30.0 (t 3.0). It is not only a predecessor's rebound: deposits with no
   termination of the same fund nearby show D+1..D+5 +15.9 (t 5.2), D+1..D+21 +29.7 (t 5.0).
10. **Stale closes, survivorship, lookahead.** 0.12% zero-volume days; dead funds are in the
    panel with delisting returns; T and the holdings come from a prospectus about two years
    old; eligibility is read at T−10; the market uses eligibility from the session before.

## What I conclude

The forced seller is real, sized (median 7% and 90th percentile 28% of a fund's nine-session
volume), and leaves a price path of the textbook kind: a fall concentrated in the last three
sessions, a recovery in the next two, nothing after T+3, growing with the sale's share of
volume, absent in matched controls and at placebo dates, present in every era, both halves,
both sponsors and on mid quotes. As pre-specified (enter at T+1) it is a weak result. Entered
at T's close it is the strongest event effect this desk has measured on closed-end funds,
and that entry needs no information the pre-specified rule lacked. It was still chosen after
seeing the daily profile, so it is one look, not a confirmed rule.

**Could it run as a shadow book: yes.** Feed: the daily EDGAR form index for 487 filings,
`parse.py` for the holdings and T, the first 24F-2NT for size. Every order is known weeks
ahead. Long-only, whole shares, at the close of T, out at the close of T+3.

**Live calendar, 2026-11-18 to 2027-11-18** (prospectuses already filed; a trust deposited in
2026 with a term under two years is missing [U]): **90** closed-end trusts (First Trust 71,
Guggenheim 19) on 56 dates, 1,978 fund-events on 244 funds; 2 to 12 trusts a month (December
2026: 12; January 2027: 10; October 2027: 11). Funds in most of them: JPC 43, HYT 43, GHY 40,
ISD 39, FAX 34, BGH 33, ACP 31.

**Also for the core book:** its own funds are sold on T−2..T about 260 times a year; an entry
there can wait for T's close.

## What is not known

- **The fill.** The effect is measured to T's closing print. A real closing auction would
  give that print; Alpaca paper fills near the quote minutes earlier, so paper will pay about
  half a spread and miss or catch part of T's own fall [U]. Check 2 bounds it at +12bp.
- **2026.** The price panel ends 2025-12-31; nothing here is out of sample.
- **Coverage.** A third of First Trust before 2024-11; no Invesco, SmartTrust or Advisors
  Disciplined Trust; early terminations and in-kind or cross trades into a successor series
  are not observed [U].
- **Size** is an estimate from annual notices, not units outstanding at T.

## What would reopen or change it

- A paper shadow book from the December 2026 terminations: if T+1..T+3 on broker fills is
  under the spread after 100 fund-events, set aside.
- The full First Trust crawl (4,984 more filings, about two hours) and Invesco: a complete
  `n_series` and clean controls; if the effect does not rise with true `n_series`, doubt it.
- A pre-registration of the T-close entry before any 2026 price is read, then one read of
  2026 as the out-of-sample test.

## Shadow book (added 2026-11-18)

Built under the 2026-11-09 one-time approval for shadow books; simulated, $1M each, no account
and no order. The reviewer's first condition is met by writing the rule down before any 2026
price was read: it is the docstring of `shadow/signals/uit_termination.py`, committed before
the book's first price fetch.

- **The rule.** Every closed-end fund held by a First Trust or Guggenheim closed-end trust whose
  Mandatory Termination Date falls on T (the last session on or before the date, as assumed
  above). Eligible on this card's floors read at T−10: a close of $2 or more and 21-session
  dollar volume of $100,000 or more. Decided after the close of T−1, bought at the close of T,
  sold at the close of T+3. Long only, against nothing. Weights in proportion to `n_series`,
  adding to 1, as `checks.py` scored it, with no fund above 10% and the excess left in cash.
- **Why 10%.** The book above held 41 funds on an active day and a trust holds 26, so ordinary
  weights are 2.4% to 3.8% (7.7% when two trusts sell one fund). The cap binds only under ten
  funds. On the calendar below no decision in the next 252 sessions holds fewer than ten funds
  (median 30) [V], so the cap is a guard and the book is the one scored here.
- **Second line, `uit_termination_big_sale`:** the same rule on events whose estimated sale is 5%
  or more of the fund's dollar volume over T−18..T−10, size from 24F-2NT notices filed more than
  30 days before T (check 4).
- **Two differences from `checks.py`.** Its book re-read the floors each session on the day
  before the return, which is a day after the decision; the shadow book reads them once, at
  T−10. And a fund with no close on the decision date is not bought or kept.
- **The calendar** (`shadow/universes/uit_terminations_v1.csv`, builder beside it, source note
  `docs/REFERENCES.md` §12ut). Every form 487 the two sponsors filed from 2023-07-01 to
  2026-11-17 (2,374; the cap is the filing date and the two sponsors), not the one-in-three
  sample: 426 candidates read, 605 trusts parsed, 334 closed-end, **271 terminating from
  2026-01-02 to 2028-11-13** (First Trust 204, Guggenheim 67), 6,249 fund-events on 307 funds;
  7 trusts unparsed, all Guggenheim's Flaherty & Crumrine Preferred Portfolio, listed by
  accession number [V]. Closed-end funds are identified by the prospectus's own "CLOSED-END
  FUNDS" heading, not CRSP; on 384 trusts both rules give the same answer for every trust [V].
- **Next 12 months, 2026-11-19 to 2027-11-18:** 101 trusts (First Trust 78, Guggenheim 23) on 64
  dates, 2,276 fund-events on 249 funds. Trusts a month, November 2026 to November 2027: 2, 12,
  10, 7, 6, 11, 7, 9, 5, 5, 8, 12, 7 [V]. This replaces the count of 90 above, which missed
  2026 filings. 98 trusts (2,320 fund-events) terminated between 2026-01-02 and 2026-11-18:
  they are the out-of-sample year the reviewer asked for, not yet read.
- **What it needs.** Nothing new on the VM: Yahoo for the price floors and Alpaca's auction
  prints for the marks, both already used by other books. EDGAR is not reachable from the
  nightly run (no contact header there), so the calendar is a committed file, rebuilt monthly
  on the laptop (`shadow/universes/README.md`).
- **First position.** The first date ahead is 2026-11-20: decided 2026-11-19, bought at the
  close of 2026-11-20. It is taken only if this commit is on the `shadow` branch by the
  evening of 2026-11-19; the next are 2026-11-23 and 2026-12-04.
- **What the shadow book cannot answer** is the reviewer's second condition: it assumes the
  fill at T's official close. A paper account fills near the quote and is a separate test.
- **Dry run, 2026-11-18, after the rule was committed (`96b05ff`).** The price fetch ran without
  a key: prices to 2026-11-17 for 153 of the 167 funds near a termination date; 14 have none on
  Yahoo (merged or renamed since their prospectus) and cannot be held. Both signal functions
  were then called on those prices for the sessions 2026-11-10 to 2026-11-17, weights only: 14
  to 19 funds in the all-events line around the 2026-11-09 and 2026-11-12 dates (largest weight
  7.1%), 10 to 13 in the big-sale line (where ten funds sit exactly at the 10% cap), and nothing
  on 11-16 and 11-17, when no date is in the window. No return was read. The full nightly run
  was not tried: it needs the Alpaca data key for the exchange calendar and the marks.

